import ssl
import urllib.parse as parse
from typing import Callable, Optional, Union

from ....helpers import Helpers
from ....transport.sse.sse_client import parse_sse_to_json
from ....transport.sockets.errors import (
    SocketClosedError,
    SocketHandshakeError,
)
from ....transport.sockets.utils import WINDOW_SIZE
from ....types import DEFAULT_ENCODING, RECORD_SEPARATOR
from ..http import request
from ..sockets.client import AIOBaseSocketClient


class AIOSSEClient(AIOBaseSocketClient):
    def __init__(
            self,
            url: str = None,
            connection_id: str = None,
            headers: Optional[dict] = None,
            proxies: Optional[dict] = None,
            ssl_context: ssl.SSLContext = None,
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        super().__init__(
            url=Helpers.websocket_to_http(url),
            connection_id=connection_id,
            is_binary=False,
            headers=headers,
            proxies=proxies,
            ssl_context=ssl_context,
            enable_trace=enable_trace,
            on_message=on_message,
            on_open=on_open,
            on_error=on_error,
            on_close=on_close)

        self._buffer = b""
        self._is_chunked = False
        self._record_separator = RECORD_SEPARATOR.encode(DEFAULT_ENCODING)

    def get_socket_headers(self):
        parsed_url = parse.urlparse(self.url)

        relative_reference = parsed_url.path

        if parsed_url.query:
            relative_reference = f"{parsed_url.path}?{parsed_url.query}"

        return [
            f"GET {relative_reference} HTTP/1.1",
            f"Host: {parsed_url.netloc.rsplit('@', 1)[-1]}",
            "Accept: text/event-stream",
            "Cache-Control: no-cache",
            "Connection: keep-alive"
        ]

    async def handshake(self) -> None:
        response = await self.read_headers()

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {response}")

        status_line = response.split(b"\r\n", 1)[0]

        if b"200" not in status_line:
            raise SocketHandshakeError(
                f"SSE handshake failed: "
                f"{response.decode(DEFAULT_ENCODING, errors='replace')}")

        self._is_chunked =\
            b"transfer-encoding: chunked" in response.lower()

    async def _read_chunk(self) -> bytes:
        line = await self.reader.readuntil(b"\r\n")
        size_hex = line[:-2].split(b";")[0].strip()

        if not size_hex:  # pragma: no cover
            return b""

        size = int(size_hex, 16)

        if size == 0:
            raise SocketClosedError()

        data = await self.reader.readexactly(size)
        await self.reader.readexactly(2)
        return data

    async def _read_more(self) -> bytes:
        if self._is_chunked:
            return await self._read_chunk()

        return await self.reader.read(WINDOW_SIZE)

    def _find_frame_end(self):
        crlf = self._buffer.find(b"\r\n\r\n")
        lf = self._buffer.find(b"\n\n")

        if crlf == -1 and lf == -1:
            return -1, 0
        if crlf == -1:
            return lf, 2
        if lf == -1:
            return crlf, 4
        return (crlf, 4) if crlf < lf else (lf, 2)

    def prepare_data(self, buffer: bytes):
        sep = self._record_separator

        if sep in buffer:
            decoded_strs = [parse_sse_to_json(x) for x in buffer.split(sep)]
            decoded_str = RECORD_SEPARATOR.join(decoded_strs)
        else:
            decoded_str = parse_sse_to_json(buffer)

        return decoded_str

    async def read_message(self):
        while True:
            idx, end_len = self._find_frame_end()

            if idx != -1:
                break

            chunk = await self._read_more()

            if not chunk:
                raise SocketClosedError()

            self._buffer += chunk

        frame_data = self._buffer[:idx]
        self._buffer = self._buffer[idx + end_len:]

        data_parts = []
        for line in frame_data.split(b"\n"):
            line = line.rstrip(b"\r")
            if line.startswith(b"data:"):
                data_parts.append(line[5:].lstrip(b" "))

        if not data_parts:  # pragma: no cover
            return None

        data = b"".join(data_parts)

        if self._record_separator in data:
            data = data[:data.rindex(self._record_separator)]

        if not data:  # pragma: no cover
            return None

        return self.prepare_data(data)

    async def send(
            self,
            message: Union[str, bytes],
            headers: dict = None):
        request_headers = {
            "Content-Type": "application/octet-stream",
        } if headers is None else headers

        request_headers.update(self.headers)

        msg_bytes = message\
            if type(message) is bytes else\
            message.encode(DEFAULT_ENCODING)

        response = await request(
            Helpers.websocket_to_http(self.url),
            method="POST",
            headers=request_headers,
            proxies=self.proxies,
            data=msg_bytes,
            ssl_context=self.ssl_context)

        self.logger.debug(
            f"SSE send response: {response.status_code} - {response.json()}")
