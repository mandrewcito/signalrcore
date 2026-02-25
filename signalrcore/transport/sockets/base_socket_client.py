import socket
import ssl
import urllib.parse as parse
import threading
from typing import Callable, Optional, Dict
from ...helpers import Helpers
from .utils import WINDOW_SIZE
from .errors import SocketHandshakeError, \
    NoHeaderException, SocketClosedError
from ...types import DEFAULT_ENCODING, CRLF, CRLF_CRLF
from ..base_client import BaseClient


class BaseSocketClient(BaseClient):
    def __init__(
            self,
            thread_name: str,
            success_status_code: bytes,
            url: str = None,
            connection_id: str = None,
            is_binary: bool = False,
            headers: Optional[Dict] = None,
            proxies: Optional[Dict] = None,
            ssl_context: ssl.SSLContext = ssl.create_default_context(),
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        self.ssl_context = ssl_context
        self.thread_name = thread_name
        self.success_status_code = success_status_code
        self.url = url
        self.connection_id = connection_id
        self.is_binary = is_binary
        self.headers = headers or {}
        self.proxies = proxies or {}
        self.enable_trace = enable_trace
        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close

        self.ssl_context = ssl_context

        self.logger = Helpers.get_logger()

        self.running: bool = False
        self.is_closing: bool = False
        self.recv_thread: threading.Thread = None
        self._lock = threading.Lock()

    def is_trace_enabled(self):
        return self.enable_trace

    def is_connection_closed(self):
        return not self.running\
            or self.recv_thread is None\
            or not self.recv_thread.is_alive()

    def get_socket_headers(self) -> str:  # pragma: no cover
        raise NotImplementedError("Clients must implement this method")

    def prepare_data(self, data):  # pragma: no cover
        raise NotImplementedError("Clients must implement data postprocessing")

    def create_socket(self):
        parsed_url = parse.urlparse(self.url)
        host, port = parsed_url.hostname, parsed_url.port
        is_secure_connection = parsed_url.scheme in ("wss", "https")
        port = Helpers.get_port(parsed_url)

        proxy_info = Helpers.get_proxy_info(
            is_secure_connection,
            self.proxies
        )

        if proxy_info is not None:
            host = proxy_info.hostname,
            port = proxy_info.port

        raw_sock = socket.create_connection((host, port))

        if is_secure_connection:
            raw_sock = self.ssl_context.wrap_socket(
                raw_sock,
                server_hostname=host)
        return raw_sock

    def connect(self):
        self.sock = self.create_socket()

        request_headers = self.get_socket_headers()

        for k, v in self.headers.items():
            request_headers.append(f"{k}: {v}")

        request = CRLF.join(request_headers) + CRLF_CRLF
        req = request.encode(DEFAULT_ENCODING)

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {req}")

        self.sock.sendall(req)

        # Read handshake response
        response = b""
        while CRLF_CRLF.encode(DEFAULT_ENCODING) not in response:
            chunk = self.sock.recv(WINDOW_SIZE)

            if not chunk:
                raise SocketHandshakeError(
                    "Connection closed during handshake")

            response += chunk

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {response}")

        if self.success_status_code not in response:
            raise SocketHandshakeError(
                f"Handshake failed: {response.decode()}")

        self.running = True
        self.recv_thread = threading.Thread(
            target=self.run,
            name=self.thread_name)
        self.recv_thread.daemon = True
        self.recv_thread.start()

    def close(self):
        if not self.running or self.is_closing:
            return

        self.is_closing = True
        self.running = False

        try:
            self.logger.debug("Base socket client: closing socket")

            self.dispose()

            self.logger.debug("Base socket client: closed successfully")
        except Exception as ex:  # pragma: no cover
            self.logger.error(ex)  # pragma: no cover
            self.on_error(ex)  # pragma: no cover
        finally:
            self.is_closing = False
            self.on_close()

    def dispose(self):
        if self.sock is not None:
            self.sock.close()

        is_same_thread = threading.current_thread().name == self.thread_name

        if self.recv_thread and not is_same_thread:
            self.recv_thread.join()
            self.recv_thread = None

    def run(self):
        self.on_open()
        try:
            while self.running:
                message = self._recv_frame()

                if self.on_message and message is not None:
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

            if (has_no_content or connection_closed) and not self.is_closing:
                self.on_close()
                return

            if (has_closed_fd or has_no_content) and self.is_closing:
                return

            self.logger.error(f"Receive error: {e}")

            self.on_error(e)

    def _recv_frame(self):  # pragma: no cover
        raise NotImplementedError()
