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
            verify_ssl: bool = True,
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
            verify_ssl=verify_ssl,
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

    def _recv_frame(self):
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

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {data}")

        return self.prepare_data(data)
