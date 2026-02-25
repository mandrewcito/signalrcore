import base64
import os
import struct
import ssl
import urllib.parse as parse

from typing import Optional, Callable, Union

from ..sockets.errors import SocketClosedError, NoHeaderException
from ..sockets.base_socket_client import BaseSocketClient
from ...types import DEFAULT_ENCODING

THREAD_NAME = "Signalrcore websocket client"


class WebSocketClient(BaseSocketClient):
    def __init__(
            self,
            url: str,
            connection_id: str = "",
            is_binary: bool = False,
            headers: Optional[dict] = None,
            proxies: dict = {},
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

        key = base64.b64encode(os.urandom(16)).decode(DEFAULT_ENCODING)
        relative_reference = parsed_url.path

        if parsed_url.query:
            relative_reference = f"{parsed_url.path}?{parsed_url.query}"
        else:
            relative_reference =\
                f"{parsed_url.path}?connectionId={self.connection_id}"

        return [
            f"GET {relative_reference} HTTP/1.1",
            f"Host: {parsed_url.hostname}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13"
        ]

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

    def _recv_exactly(self, n):
        """Receive exactly n bytes, looping over partial reads."""
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise SocketClosedError()
            data += chunk
        return data

    def _read_one_frame(self):
        """Read a single WebSocket frame. Returns (fin, opcode, data)."""
        try:
            header = self._recv_exactly(2)
        except ssl.SSLError as ex:
            self.logger.error(ex)
            raise NoHeaderException()
        except SocketClosedError:
            raise NoHeaderException()

        fin = (header[0] & 0x80) != 0
        opcode = header[0] & 0x0F
        masked_len = header[1]

        if self.logger:
            self.logger.debug(
                f"fin: {fin}, opcode: {opcode:#x}, masked_len: {masked_len}")

        if masked_len & 0x80:
            # RFC 6455 §5.1: server MUST NOT mask frames sent to the client
            try:
                self.send(struct.pack(">H", 1002), opcode=0x8)
            except Exception:
                pass
            raise SocketClosedError()

        payload_len = masked_len & 0x7F
        if payload_len == 126:
            payload_len = struct.unpack(">H", self._recv_exactly(2))[0]
        elif payload_len == 127:  # pragma: no cover
            payload_len = struct.unpack(">Q", self._recv_exactly(8))[0]

        data = self._recv_exactly(payload_len)

        return fin, opcode, data

    def _recv_frame(self):
        fin, opcode, data = self._read_one_frame()

        if opcode == 0x8:  # pragma: no cover
            raise SocketClosedError()

        payload = data
        while not fin:
            fin, cont_opcode, data = self._read_one_frame()
            if cont_opcode == 0x8:  # pragma: no cover
                raise SocketClosedError()
            payload += data

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {payload}")

        return self.prepare_data(payload)
