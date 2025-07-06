import socket
import ssl
import base64
import threading
import os
import struct
from typing import Optional, Callable, Union
from signalrcore.helpers import Helpers


THREAD_NAME = "Signalrcore websocket client"
WINDOW_SIZE = 1024


class NoHeaderException(Exception):
    """Error reading messages from socket, empty content
    """
    pass


class SocketHandshakeError(Exception):
    """Error during connection

    Args:
        msg (str): message
    """
    def __init__(self, msg: str):
        super().__init__(msg)


class WebSocketClient(object):
    """Minimal websocket client

    Args:
        url (str): Websocket url
        headers (Optional[dict]): additional headers
        verify_ssl (bool): Verify SSL y/n
        on_message (callable): on message callback
        on_error (callable): on error callback
        on_open (callable): on open callback
        on_close (callable): on close callback
    """
    def __init__(
            self,
            url: str,
            is_binary: bool = False,
            headers: Optional[dict] = None,
            verify_ssl: bool = True,
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        self.is_trace_enabled = enable_trace
        self.url = url
        self.is_binary = is_binary
        self.headers = headers or {}
        self.verify_ssl = verify_ssl
        self.sock = None
        self.ssl_context = ssl.create_default_context()\
            if verify_ssl else\
            ssl._create_unverified_context()
        self.logger = Helpers.get_logger()
        self.recv_thread = None
        self.on_message = on_message
        self.on_close = on_close
        self.on_error = on_error
        self.on_open = on_open
        self.running = False
        self.is_closing = False

    def connect(self):
        # ToDo URL PARSE
        scheme, rest = self.url.split("://", 1)
        host_port, path = rest.split("/", 1)
        path = "/" + path

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 443 if scheme == "wss" else 80
        raw_sock = socket.create_connection((host, port))
        if scheme == "wss" or scheme == "https":
            raw_sock = self.ssl_context.wrap_socket(
                raw_sock,
                server_hostname=host)

        self.sock = raw_sock

        # Perform the WebSocket handshake
        key = base64.b64encode(os.urandom(16)).decode("utf-8")
        request_headers = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13"
        ]
        for k, v in self.headers.items():
            request_headers.append(f"{k}: {v}")

        request = "\r\n".join(request_headers) + "\r\n\r\n"
        req = request.encode("utf-8")

        if self.is_trace_enabled:
            self.logger.debug(req)

        self.sock.sendall(req)

        # Read handshake response
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(WINDOW_SIZE)
            if self.is_trace_enabled:
                self.logger.debug(chunk)

            if not chunk:
                raise SocketHandshakeError(
                    "Connection closed during handshake")

            response += chunk

        if b"101" not in response:
            raise SocketHandshakeError(
                f"Handshake failed: {response.decode()}")

        self.running = True
        self.recv_thread = threading.Thread(
            target=self._recv_loop,
            name=THREAD_NAME)
        self.recv_thread.daemon = True
        self.recv_thread.start()

    def _recv_loop(self):
        self.on_open()
        try:
            while self.running:
                message = self._recv_frame()

                if self.on_message:
                    self.on_message(self, message)
        except Exception as e:
            self.running = False

            # is closing and no header indicates
            # that socket has not received anything
            has_no_content = type(e) is NoHeaderException

            # is closing and errno indicates
            # that file descriptor points to a closed file
            has_closed_fd = type(e) is OSError and e.errno == 9

            if (has_no_content or has_closed_fd) and self.is_closing:
                return

            if self.logger:
                self.logger.error(f"Receive error: {e}")
            self.on_error(e)

    def _recv_frame(self):
        # Very basic, single-frame, unfragmented
        header = self.sock.recv(2)
        if not header:
            raise NoHeaderException()

        fin_opcode = header[0]
        masked_len = header[1]

        if self.logger:
            self.logger.debug(
                f"fin opcode: {fin_opcode}, masked len: {masked_len}")

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
            self.logger.debug(data)

        if self.is_binary:
            return data

        return data.decode("utf-8")

    def send(
            self,
            message: Union[str, bytes],
            opcode=0x1):
        # Text or binary opcode (no fragmentation)
        payload = message.encode("utf-8")\
            if type(message) is str else message
        header = bytes([0x80 | opcode])
        length = len(payload)
        if length <= 125:
            header += bytes([0x80 | length])
        elif length <= 65535:
            header += bytes([0x80 | 126]) + struct.pack(">H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", length)

        # Mask the payload
        masking_key = os.urandom(4)
        masked_payload = bytes(
            b ^ masking_key[i % 4]
            for i, b in enumerate(payload))
        frame = header + masking_key + masked_payload
        self.sock.sendall(frame)

    def dispose(self):
        if self.sock:
            self.sock.close()
        is_same_thread = threading.current_thread().name == THREAD_NAME
        if self.recv_thread and not is_same_thread:
            self.recv_thread.join()
            self.recv_thread = None

    def close(self):
        self.logger.debug("Start closing socket")
        try:
            self.is_closing = True
            self.running = False

            self.dispose()

            self.on_close()
            self.logger.debug("socket closed successfully")
        except Exception as ex:
            self.logger.error(ex)
            self.on_error(ex)
        finally:
            self.is_closing = False
