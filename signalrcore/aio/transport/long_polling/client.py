import asyncio
import contextlib
import ssl
from typing import Callable, List, Optional, Union

from ....helpers import Helpers
from ....types import DEFAULT_ENCODING, RECORD_SEPARATOR
from ...utils import call_callback
from ..http import request

# The server holds long polling requests for up to ~90 seconds, so the
# client timeout must be slightly higher to let the poll finish.
REQUEST_TIMEOUT = 100
DISPOSE_CANCEL_TIMEOUT = 5


class AIOLongPollingBaseClient(object):
    def __init__(
            self,
            url: str,
            receive_header: str,
            connection_id: str = None,
            headers: Optional[dict] = None,
            proxies: Optional[dict] = None,
            ssl_context: ssl.SSLContext = None,
            enable_trace: bool = False,
            timeout: float = REQUEST_TIMEOUT,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        self.url = url
        self.connection_id = connection_id
        self.headers = headers if headers is not None else {}
        self.proxies = proxies if proxies is not None else {}
        self.ssl_context = ssl_context
        self.enable_trace = enable_trace
        self.timeout = timeout
        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close
        self._receive_headers = {"Accept": receive_header}

        self.logger = Helpers.get_logger()
        self._running = False
        self.is_closing = False
        self._recv_task: Optional[asyncio.Task] = None

        self._buffer = b""
        self._byte_separator = RECORD_SEPARATOR.encode(DEFAULT_ENCODING)

    def is_connection_closed(self) -> bool:
        return not self._running\
            or self._recv_task is None\
            or self._recv_task.done()

    def is_trace_enabled(self):
        return self.enable_trace

    async def connect(self) -> None:
        self._running = True
        self._recv_task = asyncio.create_task(self.run())

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
            timeout=self.timeout,
            ssl_context=self.ssl_context)

        self.logger.debug(
            "Long Polling send response: "
            f"{response.status_code} - {response.json()}")

    async def _recv_frame(self) -> Union[str, bytes, None]:
        try:
            response = await request(
                Helpers.websocket_to_http(self.url),
                method="GET",
                headers=self._receive_headers,
                proxies=self.proxies,
                params={"id": self.connection_id},
                timeout=self.timeout,
                ssl_context=self.ssl_context)
        except asyncio.TimeoutError:
            return None

        status_code, data = response.status_code, response.content

        if status_code == 204:
            raise OSError("Connection closed by server (204)")

        if status_code in (400, 404):
            raise OSError(
                f"Connection closed by server ({status_code})")

        if status_code != 200:
            raise OSError(
                f"Unexpected long polling status {status_code}")

        if self.enable_trace:
            self.logger.debug(f"[TRACE] {data}")

        return data

    def _append(self, frame: bytes) -> List[bytes]:
        self._buffer += frame
        complete_buffers = []

        while self._byte_separator in self._buffer:
            idx = self._buffer.index(self._byte_separator)
            complete_buffers.append(self._buffer[0: idx])
            self._buffer = self._buffer[idx + len(self._byte_separator):]

        return complete_buffers

    def prepare_data(self, data: bytes) -> Union[bytes, str]:
        return data

    async def run(self) -> None:
        try:
            await call_callback(self.on_open)

            while self._running:
                frame = await self._recv_frame()

                if frame is not None:
                    for complete_buffer in self._append(frame):
                        if not complete_buffer:
                            continue

                        message = self.prepare_data(complete_buffer)
                        if self.on_message is not None:
                            await call_callback(
                                self.on_message, self, message)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._running = False

            if self.logger:
                self.logger.error(f"Receive error: {error}")

            if isinstance(error, OSError):
                await call_callback(self.on_close)
            elif self.on_error is not None:
                await call_callback(self.on_error, error)

    async def dispose(self) -> None:
        self._running = False

        task = self._recv_task

        if task is not None\
                and task is not asyncio.current_task()\
                and not task.done():
            task.cancel()
            with contextlib.suppress(
                    asyncio.CancelledError, Exception):
                await asyncio.wait_for(task, timeout=DISPOSE_CANCEL_TIMEOUT)

        self._recv_task = None

    async def close(self) -> None:
        if not self._running:
            return

        self.logger.debug("Long polling closing connection")
        self.is_closing = True
        self._running = False

        try:
            response = await request(
                Helpers.websocket_to_http(self.url),
                method="DELETE",
                headers=self.headers,
                proxies=self.proxies,
                params={"id": self.connection_id},
                timeout=self.timeout,
                ssl_context=self.ssl_context)

            if response.status_code not in (200, 202):
                self.logger.error(
                    "Error removing connection from the server "
                    f"{response.json()}")
        except Exception as error:
            self.logger.error(error)
        finally:
            await self.dispose()
            self.is_closing = False
            await call_callback(self.on_close)


class AIOLongPollingTextClient(AIOLongPollingBaseClient):
    def __init__(self, **kwargs):
        super().__init__(receive_header="Text", **kwargs)

    def prepare_data(self, data):
        return data.decode(DEFAULT_ENCODING)


class AIOLongPollingBinaryClient(AIOLongPollingBaseClient):
    def __init__(self, **kwargs):
        super().__init__(receive_header="binary", **kwargs)
