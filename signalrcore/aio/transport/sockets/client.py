import asyncio
import contextlib
import ssl
import urllib.parse as parse
from typing import Callable, Dict, Optional, Union

from ....helpers import Helpers
from ....types import CRLF_CRLF, DEFAULT_ENCODING
from ....transport.sockets.errors import (
    NoHeaderException,
    SocketClosedError,
)
from ....transport.sockets.utils import create_ssl_context
from ...utils import call_callback
from ..http import _open_connection

WINDOW_SIZE = 1024


class AIOBaseSocketClient(object):
    """Base for asyncio socket based transports (WebSocket and SSE)."""

    def __init__(
            self,
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
        self.running = False
        self.is_closing = False
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.recv_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()

    def is_trace_enabled(self) -> bool:
        return self.enable_trace

    def is_connection_closed(self) -> bool:
        return not self.running\
            or self.recv_task is None\
            or self.recv_task.done()

    def get_socket_headers(self):
        raise NotImplementedError()

    def validate_handshake_response(self, response: bytes) -> None:
        pass

    async def open_stream(self):
        parsed = parse.urlparse(self.url)
        secure = parsed.scheme in ("https", "wss")
        proxy_info = Helpers.get_proxy_info(secure, self.proxies)

        return await _open_connection(
            parsed,
            proxy_info,
            self.ssl_context if secure else None,
            secure)

    async def read_headers(self) -> bytes:
        return await self.reader.readuntil(
            CRLF_CRLF.encode(DEFAULT_ENCODING))

    async def connect(self) -> None:
        self.reader, self.writer = await self.open_stream()

        try:
            request_headers = self.get_socket_headers()

            for key, value in self.headers.items():
                request_headers.append(f"{key}: {value}")

            request = "\r\n".join(request_headers) + CRLF_CRLF
            payload = request.encode(DEFAULT_ENCODING)

            if self.is_trace_enabled():
                self.logger.debug(f"[TRACE] - {payload}")

            self.writer.write(payload)
            await self.writer.drain()

            await self.handshake()
        except BaseException:
            self.writer.close()
            with contextlib.suppress(
                    AttributeError, ConnectionError, OSError):
                await self.writer.wait_closed()
            self.writer = None
            self.reader = None
            raise

        self.running = True
        self.recv_task = asyncio.create_task(self.run())

    async def handshake(self) -> None:
        response = await self.read_headers()

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {response}")

        self.validate_handshake_response(response)

    async def read_message(self):
        raise NotImplementedError()

    async def run(self) -> None:
        try:
            await call_callback(self.on_open)

            while self.running:
                message = await self.read_message()

                if self.on_message is not None and message is not None:
                    await call_callback(self.on_message, self, message)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.running = False

            if self.is_closing:
                return

            if isinstance(
                    error,
                    (SocketClosedError, NoHeaderException, OSError)):
                await call_callback(self.on_close)
                return

            self.logger.error(f"Receive error: {error}")
            if self.on_error is not None:
                await call_callback(self.on_error, error)
        finally:
            self._close_transport()

    def _close_transport(self) -> None:
        if self.writer is not None:
            self.writer.close()

    async def send_bytes(self, payload: bytes) -> None:
        if self.is_connection_closed():
            raise SocketClosedError()

        async with self._write_lock:
            if self.writer is None:
                raise SocketClosedError()
            self.writer.write(payload)
            await self.writer.drain()

    async def send(self, message: Union[str, bytes], **kwargs) -> None:
        raise NotImplementedError()

    async def close(self) -> None:
        if not self.running or self.is_closing:
            return

        self.is_closing = True
        self.running = False

        try:
            await self.dispose()
        except Exception as error:  # pragma: no cover
            self.logger.error(error)
            if self.on_error is not None:
                await call_callback(self.on_error, error)
        finally:
            self.is_closing = False
            await call_callback(self.on_close)

    async def dispose(self) -> None:
        if self.writer is not None:
            self.writer.close()

            with contextlib.suppress(
                    AttributeError, ConnectionError, OSError):
                await self.writer.wait_closed()

        task = self.recv_task

        if task is not None\
                and task is not asyncio.current_task()\
                and not task.done():
            task.cancel()
            with contextlib.suppress(
                    asyncio.CancelledError, Exception):
                await task

        self.recv_task = None
