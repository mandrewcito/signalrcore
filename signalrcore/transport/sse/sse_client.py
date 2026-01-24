import ssl
import socket
import threading
import struct
import urllib.parse as parse

from typing import Callable, Union

from ...helpers import Helpers
from ...helpers import RequestHelpers
from ..sockets.utils import WINDOW_SIZE
from ..sockets.errors import SocketHandshakeError, \
    NoHeaderException, SocketClosedError

THREAD_NAME = "Signalrcore SSE client"


class SSEClient(object):
    def __init__(
            self,
            url: str = None,
            connection_id: str = None,
            headers: dict = dict(),
            proxies: dict = dict(),
            verify_ssl: bool = True,
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        self.url = Helpers.websocket_to_http(url)
        self.connection_id = connection_id
        self.headers = headers
        self.proxies = proxies
        self.verify_ssl = verify_ssl
        self.enable_trace = enable_trace
        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close

        self.ssl_context = ssl.create_default_context()\
            if verify_ssl else\
            ssl._create_unverified_context()
        self.logger = Helpers.get_logger()

        self.running = False
        self.is_closing = False

    def is_trace_enabled(self):
        return self.enable_trace

    def connect(self):
        parsed_url = parse.urlparse(self.url)
        host, port = parsed_url.hostname, parsed_url.port
        is_secure_connection = parsed_url.scheme in ("wss", "https")
        port = Helpers.get_port(parsed_url)
        proxy_info = None

        if is_secure_connection\
                and self.proxies.get("https", None) is not None:
            proxy_info = parse.urlparse(self.proxies.get("https"))

        if not is_secure_connection\
                and self.proxies.get("http", None) is not None:
            proxy_info = parse.urlparse(self.proxies.get("http"))

        if proxy_info is not None:
            host = proxy_info.hostname,
            port = proxy_info.port

        raw_sock = socket.create_connection((host, port))

        if is_secure_connection:
            raw_sock = self.ssl_context.wrap_socket(
                raw_sock,
                server_hostname=host)

        self.sock = raw_sock
        relative_reference = parsed_url.path

        if parsed_url.query:
            relative_reference = f"{parsed_url.path}?{parsed_url.query}"

        request_headers = [
            f"GET {relative_reference} HTTP/1.1",
            f"Host: {parsed_url.hostname}",
            "Accept: text/event-stream",
            "Cache-Control: no-cache",
            "Connection: keep-alive"
        ]

        for k, v in self.headers.items():
            request_headers.append(f"{k}: {v}")

        request = "\r\n".join(request_headers) + "\r\n\r\n"
        req = request.encode("utf-8")

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {req}")

        self.sock.sendall(req)

        # Read handshake response
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(WINDOW_SIZE)

            if not chunk:
                raise SocketHandshakeError(
                    "Connection closed during handshake")

            response += chunk

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {response}")

        if b"200" not in response:
            raise SocketHandshakeError(
                f"Handshake failed: {response.decode()}")

        self.running = True
        self.recv_thread = threading.Thread(
            target=self.run,
            name=THREAD_NAME)
        self.recv_thread.daemon = True
        self.recv_thread.start()

    def close(self):
        try:
            self.is_closing = True
            self.running = False

            self.logger.debug("SSE closing socket")

            self.dispose()

            self.on_close()

            self.logger.debug("SSE closed successfully")
        except Exception as ex:  # pragma: no cover
            self.logger.error(ex)  # pragma: no cover
            self.on_error(ex)  # pragma: no cover
        finally:
            self.is_closing = False

    def dispose(self):
        if self.sock:
            self.sock.close()

        is_same_thread = threading.current_thread().name == THREAD_NAME

        if self.recv_thread and not is_same_thread:
            self.recv_thread.join()
            self.recv_thread = None

    def send(
            self,
            message: Union[str, bytes],
            headers: dict = None):

        headers = {
            "Content-Type": "application/octet-stream",
        } if headers is None else headers

        headers.update(self.headers)

        status_code, response = RequestHelpers.post(
            Helpers.websocket_to_http(self.url),
            headers,
            self.proxies,
            self.verify_ssl,
            message if type(message) is bytes else message.encode("utf-8")
        )

        self.logger.debug(f"SSE send response: {status_code} - {response}")

    def run(self):
        self.on_open()
        try:
            while self.running:
                message = self._recv_frame()
                print(message)
                if self.on_message:
                    self.on_message(self, message)
        except (OSError, Exception) as e:
            self.running = False

            # is closing and no header indicates
            # that socket has not received anything
            has_no_content = type(e) is NoHeaderException

            # is closing and errno indicates
            # that file descriptor points to a closed file
            has_closed_fd = type(e) is OSError and e.errno == 9

            # closed by the server
            connection_closed = has_closed_fd or type(e) is SocketClosedError

            if connection_closed and not self.is_closing:
                raise e  # pragma: no cover

            if (has_closed_fd or has_no_content) and self.is_closing:
                return

            if self.logger:
                self.logger.error(f"Receive error: {e}")

            self.on_error(e)

    def _recv_frame(self):
        # Very basic, single-frame, unfragmented
        try:
            header = self.sock.recv(2)
        except ssl.SSLError as ex:
            self.logger.error(ex)
            header = None

        if header is None or len(header) < 2:
            raise NoHeaderException()

        fin_opcode = header[0]
        masked_len = header[1]

        if self.logger:
            self.logger.debug(
                f"fin opcode: {fin_opcode}, masked len: {masked_len}")

        if fin_opcode == 8:
            raise SocketClosedError(header)
        payload_len = masked_len & 0x7F
        if payload_len == 126:
            payload_len = struct.unpack(">H", self.sock.recv(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", self.sock.recv(8))[0]

        if masked_len & 0x80:
            masking_key = self.sock.recv(4)
            masked_data = self.sock.recv(payload_len)
            data = bytes(
                b ^ masking_key[i % 4]
                for i, b in enumerate(masked_data))
        else:
            data = self.sock.recv(payload_len)

        if self.is_trace_enabled:
            self.logger.debug(f"[TRACE] - {data}")
        return data[1:].decode("utf-8")
