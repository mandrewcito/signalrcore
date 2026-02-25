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
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise SocketClosedError()
            data += chunk
        return data

    def _recv_frame(self):
        message_data = b""
        while True:
            try:
                header = self._recv_exactly(2)
            except ssl.SSLError as ex:
                self.logger.error(ex)
                header = None

            if header is None or len(header) < 2:
                raise NoHeaderException()

            fin_opcode = header[0]
            fin = fin_opcode & 0x80
            opcode = fin_opcode & 0x0F

            masked_len = header[1]
            mask_len = masked_len & 0x80
            payload_len = masked_len & 0x7F
            if payload_len == 126:
                payload_len = struct.unpack(">H", self._recv_exactly(2))[0]
            elif payload_len == 127:
                payload_len = struct.unpack(">Q", self._recv_exactly(8))[0]

            if self.logger:
                self.logger.debug(
                    f"fin opcode: {fin_opcode} ({fin}:{opcode}), masked len: {masked_len} ({mask_len}:{payload_len})")

            if opcode == 8:
                raise SocketClosedError(header)

            # Handle PING (9) and PONG (10) control frames
            if opcode == 9 or opcode == 10:
                if mask_len:
                    self._recv_exactly(4 + payload_len) # Skip mask and payload
                else:
                    self._recv_exactly(payload_len) # Skip payload
                continue # Wait for next frame

            if mask_len:
                masking_key = self._recv_exactly(4)
                masked_data = self._recv_exactly(payload_len)
                data = bytes(
                    b ^ masking_key[i % 4]
                    for i, b in enumerate(masked_data))
            else:
                data = self._recv_exactly(payload_len)

            if self.is_trace_enabled():
                self.logger.debug(f"[TRACE] [{len(data)}] {data}")
            message_data += data

            if fin:
                break

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] [{len(message_data)}] {message_data}")

        return self.prepare_data(message_data)
