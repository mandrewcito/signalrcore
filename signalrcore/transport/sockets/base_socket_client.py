import base64
import socket
import ssl
import urllib.parse as parse
import threading
from typing import Callable, Optional, Dict
from ...helpers import Helpers
from .utils import WINDOW_SIZE, create_ssl_context
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
            ssl_context: ssl.SSLContext = None,
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        self.ssl_context = ssl_context\
            if ssl_context is not None else\
            create_ssl_context(True)
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

        self.logger = Helpers.get_logger()

        self.running: bool = False
        self.is_closing: bool = False
        self.sock: Optional[socket.socket] = None
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

    def validate_handshake_response(self, response: bytes):
        """Validate protocol specific handshake headers.

        Subclasses may raise SocketHandshakeError when the response is
        not acceptable. The default implementation accepts everything.
        """
        pass

    def prepare_data(self, data):  # pragma: no cover
        raise NotImplementedError("Clients must implement data postprocessing")

    def create_socket(self):
        parsed_url = parse.urlparse(self.url)
        host = parsed_url.hostname
        port = Helpers.get_port(parsed_url)
        is_secure_connection = parsed_url.scheme in ("wss", "https")

        proxy_info = Helpers.get_proxy_info(
            is_secure_connection,
            self.proxies
        )

        if proxy_info is None:
            raw_sock = socket.create_connection((host, port))

            if is_secure_connection:
                raw_sock = self.ssl_context.wrap_socket(
                    raw_sock,
                    server_hostname=host)
            return raw_sock

        proxy_host = proxy_info.hostname
        proxy_port = proxy_info.port or\
            (443 if proxy_info.scheme == "https" else 80)

        raw_sock = socket.create_connection((proxy_host, proxy_port))

        # Secure connections must tunnel through the proxy, otherwise
        # TLS would be negotiated with the proxy instead of the
        # SignalR server.
        if is_secure_connection:
            self._tunnel_through_proxy(
                raw_sock, proxy_info, host, port)
            raw_sock = self.ssl_context.wrap_socket(
                raw_sock,
                server_hostname=host)

        return raw_sock

    def _tunnel_through_proxy(
            self,
            sock,
            proxy_info,
            host: str,
            port: int):
        target = f"{host}:{port}"

        headers = [
            f"CONNECT {target} HTTP/1.1",
            f"Host: {target}"
        ]

        if proxy_info.username is not None:
            username = parse.unquote(proxy_info.username)
            password = parse.unquote(proxy_info.password or "")
            credentials = base64.b64encode(
                f"{username}:{password}".encode(DEFAULT_ENCODING)
            ).decode(DEFAULT_ENCODING)
            headers.append(f"Proxy-Authorization: Basic {credentials}")

        request = CRLF.join(headers) + CRLF_CRLF
        sock.sendall(request.encode(DEFAULT_ENCODING))

        response = b""
        response_delimiter = CRLF_CRLF.encode(DEFAULT_ENCODING)

        while response_delimiter not in response:
            chunk = sock.recv(WINDOW_SIZE)

            if not chunk:
                raise SocketHandshakeError(
                    "Connection closed during proxy handshake")

            response += chunk

        status_line = response.split(
            CRLF.encode(DEFAULT_ENCODING), 1)[0].decode(
                DEFAULT_ENCODING,
                errors="replace")

        status_parts = status_line.split()

        if len(status_parts) < 2 or status_parts[1] != "200":
            raise SocketHandshakeError(
                f"Proxy handshake failed: {status_line}")

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

        self.validate_handshake_response(response)

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
        try:
            self.on_open()

            while self.running:
                message = self._recv_frame()

                if self.on_message and message is not None:
                    self.on_message(self, message)

        except Exception as e:
            self.running = False

            # is closing and no header indicates
            # that socket has not received anything
            has_no_content = isinstance(e, NoHeaderException)

            # closed by the server, or the socket/SSL layer raised an
            # OSError subclass (ConnectionResetError,
            # BrokenPipeError, ssl.SSLError...). All of them mean the
            # connection is gone and reconnection must be triggered.
            connection_closed = isinstance(e, (SocketClosedError, OSError))

            if (has_no_content or connection_closed) and not self.is_closing:
                self.on_close()
                return

            if (has_no_content or connection_closed) and self.is_closing:
                return

            self.logger.error(f"Receive error: {e}")

            self.on_error(e)
        finally:
            # The receive loop owns the socket: when it ends, the
            # socket must not stay open (on_open failures included).
            self._close_socket()

    def _close_socket(self):
        if self.sock is None:
            return

        try:
            self.sock.close()
        except Exception as ex:  # pragma: no cover
            self.logger.debug(f"Error closing socket: {ex}")

    def _recv_frame(self):  # pragma: no cover
        raise NotImplementedError()
