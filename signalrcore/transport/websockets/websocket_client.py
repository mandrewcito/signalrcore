import base64
import os
import ssl
import struct
import urllib.parse as parse

from typing import Optional, Callable, Union

from ..sockets.errors import\
    SocketClosedError, NoHeaderException, SocketHandshakeError
from ..sockets.base_socket_client import BaseSocketClient
from ...types import DEFAULT_ENCODING
from . import framing
from .framing import (
    MAX_PAYLOAD_SIZE,
    build_frame,
    parse_handshake_headers,
    websocket_accept)

# Kept as a module attribute for backwards compatibility.
WEBSOCKET_GUID = framing.WEBSOCKET_GUID

THREAD_NAME = "Signalrcore websocket client"


class WebSocketClient(BaseSocketClient):
    def __init__(
            self,
            url: str,
            connection_id: str = "",
            is_binary: bool = False,
            headers: Optional[dict] = None,
            proxies: Optional[dict] = None,
            ssl_context: ssl.SSLContext = None,
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        super(WebSocketClient, self).__init__(
            thread_name=THREAD_NAME,
            success_status_code=b"101",
            url=url,
            connection_id=connection_id,
            is_binary=is_binary,
            headers=headers,
            proxies=proxies,
            ssl_context=ssl_context,
            enable_trace=enable_trace,
            on_message=on_message,
            on_open=on_open,
            on_error=on_error,
            on_close=on_close
        )

    def get_socket_headers(self):
        parsed_url = parse.urlparse(self.url)

        # A custom key is honored if the caller provided one, otherwise
        # generate a new one and keep it to validate the accept header.
        key = self.headers.get("Sec-WebSocket-Key")\
            or self.headers.get("sec-websocket-key")\
            or base64.b64encode(os.urandom(16)).decode(DEFAULT_ENCODING)
        self._websocket_key = key

        relative_reference = parsed_url.path

        if parsed_url.query:
            relative_reference = f"{parsed_url.path}?{parsed_url.query}"
        else:
            relative_reference =\
                f"{parsed_url.path}?connectionId={self.connection_id}"

        return [
            f"GET {relative_reference} HTTP/1.1",
            f"Host: {self._host_header(parsed_url)}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13"
        ]

    @staticmethod
    def _host_header(parsed_url) -> str:
        # netloc keeps non-default ports and IPv6 brackets; strip any
        # user information that may be present in the URL.
        return parsed_url.netloc.rsplit("@", 1)[-1]\
            or parsed_url.hostname

    @staticmethod
    def _parse_handshake_headers(response: bytes) -> dict:
        return parse_handshake_headers(response)

    def validate_handshake_response(self, response: bytes):
        key = getattr(self, "_websocket_key", None)

        if key is None:  # pragma: no cover
            raise SocketHandshakeError(
                "Sec-WebSocket-Key was not generated")

        accept = self._parse_handshake_headers(
            response).get("sec-websocket-accept")

        if accept is None:
            raise SocketHandshakeError(
                "Missing Sec-WebSocket-Accept header")

        expected = websocket_accept(key)

        if accept != expected:
            raise SocketHandshakeError(
                f"Invalid Sec-WebSocket-Accept: {accept}")

    def prepare_data(self, data):
        if self.is_binary:
            return data
        return data.decode(DEFAULT_ENCODING)

    def send(
            self,
            message: Union[str, bytes],
            opcode=0x1):

        if self.is_connection_closed():
            raise SocketClosedError()

        # Text or binary opcode (no fragmentation)
        payload = message.encode(DEFAULT_ENCODING)\
            if type(message) is str else message
        self.sock.sendall(build_frame(payload, opcode))

    def _recv_exactly(self, n):
        """Receive exactly n bytes, looping over partial reads."""
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:  # pragma: no cover
                raise SocketClosedError()
            data += chunk
        return data

    def _read_one_frame(self):
        """Read a single WebSocket frame. Returns (fin, opcode, data)."""
        try:
            header = self._recv_exactly(2)
        except ssl.SSLError as ex:  # pragma: no cover
            self.logger.error(ex)
            raise NoHeaderException()
        except SocketClosedError:  # pragma: no cover
            raise NoHeaderException()

        fin = (header[0] & 0x80) != 0
        opcode = header[0] & 0x0F
        masked_len = header[1]

        if self.logger:
            self.logger.debug(
                f"fin: {fin}, opcode: {opcode:#x}, masked_len: {masked_len}")

        if masked_len & 0x80:  # pragma: no cover
            # RFC 6455 §5.1: server MUST NOT mask frames sent to the client
            self._send_control_frame(0x8, struct.pack(">H", 1002))
            raise SocketClosedError()

        payload_len = masked_len & 0x7F
        if payload_len == 126:
            payload_len = struct.unpack(">H", self._recv_exactly(2))[0]
        elif payload_len == 127:  # pragma: no cover
            payload_len = struct.unpack(">Q", self._recv_exactly(8))[0]

        if payload_len > MAX_PAYLOAD_SIZE:
            # Do not allocate/read an unbounded payload.
            self._send_control_frame(0x8, struct.pack(">H", 1009))
            raise SocketClosedError()

        data = self._recv_exactly(payload_len)

        return fin, opcode, data

    def _send_control_frame(self, opcode, data=b""):
        try:
            self.send(data, opcode=opcode)
        except Exception as ex:  # pragma: no cover
            # The connection may already be gone; reading will fail soon.
            self.logger.debug(
                f"Unable to send control frame {opcode:#x}: {ex}")

    def _recv_frame(self):
        payload = b""
        message_started = False

        while True:
            fin, opcode, data = self._read_one_frame()

            if opcode == 0x9:  # ping -> pong with the same payload
                self._send_control_frame(0xA, data)
                continue

            if opcode == 0xA:  # pong -> ignore
                continue

            if opcode == 0x8:  # close
                raise SocketClosedError()

            if opcode in (0x1, 0x2):  # text / binary
                if message_started:  # pragma: no cover
                    self._send_control_frame(0x8, struct.pack(">H", 1002))
                    raise SocketClosedError()

                payload = data
                message_started = True
            elif opcode == 0x0:  # continuation
                if not message_started:  # pragma: no cover
                    self._send_control_frame(0x8, struct.pack(">H", 1002))
                    raise SocketClosedError()

                payload += data
            else:  # pragma: no cover
                self._send_control_frame(0x8, struct.pack(">H", 1002))
                raise SocketClosedError()

            if len(payload) > MAX_PAYLOAD_SIZE:  # pragma: no cover
                self._send_control_frame(0x8, struct.pack(">H", 1009))
                raise SocketClosedError()

            if fin:
                break

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {payload}")

        return self.prepare_data(payload)
