import asyncio
import base64
import os
import struct
import ssl
import urllib.parse as parse
from typing import Callable, Optional, Union

from ....transport.websockets.framing import (
    MAX_PAYLOAD_SIZE,
    build_frame,
    parse_handshake_headers,
    websocket_accept,
)
from ....transport.sockets.errors import (
    NoHeaderException,
    SocketClosedError,
    SocketHandshakeError,
)
from ....types import DEFAULT_ENCODING
from ..sockets.client import AIOBaseSocketClient


class AIOWebSocketClient(AIOBaseSocketClient):
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
        super().__init__(
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
            on_close=on_close)

    def get_socket_headers(self):
        parsed_url = parse.urlparse(self.url)

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
        return parsed_url.netloc.rsplit("@", 1)[-1]\
            or parsed_url.hostname

    async def handshake(self) -> None:
        response = await self.read_headers()

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {response}")

        if b"101" not in response.split(b"\r\n", 1)[0]:
            raise SocketHandshakeError(
                f"Handshake failed: "
                f"{response.decode(DEFAULT_ENCODING, errors='replace')}")

        self.validate_handshake_response(response)

    def validate_handshake_response(self, response: bytes):
        key = getattr(self, "_websocket_key", None)

        if key is None:  # pragma: no cover
            raise SocketHandshakeError(
                "Sec-WebSocket-Key was not generated")

        accept = parse_handshake_headers(
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

    async def send(
            self,
            message: Union[str, bytes],
            opcode=0x1):
        payload = message.encode(DEFAULT_ENCODING)\
            if type(message) is str else message
        await self.send_bytes(build_frame(payload, opcode))

    async def _send_control_frame(self, opcode, data=b""):
        try:
            await self.send(data, opcode=opcode)
        except Exception as error:  # pragma: no cover
            self.logger.debug(
                f"Unable to send control frame {opcode:#x}: {error}")

    async def _read_one_frame(self):
        try:
            header = await self.reader.readexactly(2)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            raise NoHeaderException()

        fin = (header[0] & 0x80) != 0
        opcode = header[0] & 0x0F
        masked_len = header[1]

        self.logger.debug(
            f"fin: {fin}, opcode: {opcode:#x}, masked_len: {masked_len}")

        if masked_len & 0x80:  # pragma: no cover
            await self._send_control_frame(0x8, struct.pack(">H", 1002))
            raise SocketClosedError()

        payload_len = masked_len & 0x7F

        try:
            if payload_len == 126:
                payload_len = struct.unpack(
                    ">H", await self.reader.readexactly(2))[0]
            elif payload_len == 127:  # pragma: no cover
                payload_len = struct.unpack(
                    ">Q", await self.reader.readexactly(8))[0]

            if payload_len > MAX_PAYLOAD_SIZE:
                await self._send_control_frame(
                    0x8, struct.pack(">H", 1009))
                raise SocketClosedError()

            data = await self.reader.readexactly(payload_len)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            raise NoHeaderException()

        return fin, opcode, data

    async def read_message(self):
        payload = b""
        message_started = False

        while True:
            fin, opcode, data = await self._read_one_frame()

            if opcode == 0x9:  # ping -> pong with the same payload
                await self._send_control_frame(0xA, data)
                continue

            if opcode == 0xA:  # pong -> ignore
                continue

            if opcode == 0x8:  # close
                raise SocketClosedError()

            if opcode in (0x1, 0x2):  # text / binary
                if message_started:  # pragma: no cover
                    await self._send_control_frame(
                        0x8, struct.pack(">H", 1002))
                    raise SocketClosedError()

                payload = data
                message_started = True
            elif opcode == 0x0:  # continuation
                if not message_started:  # pragma: no cover
                    await self._send_control_frame(
                        0x8, struct.pack(">H", 1002))
                    raise SocketClosedError()

                payload += data
            else:  # pragma: no cover
                await self._send_control_frame(
                    0x8, struct.pack(">H", 1002))
                raise SocketClosedError()

            if len(payload) > MAX_PAYLOAD_SIZE:  # pragma: no cover
                await self._send_control_frame(
                    0x8, struct.pack(">H", 1009))
                raise SocketClosedError()

            if fin:
                break

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {payload}")

        return self.prepare_data(payload)
