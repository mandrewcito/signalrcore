import asyncio
import contextlib
import ssl
import time
import traceback
from typing import Callable, Dict, Optional

from ...helpers import Helpers
from ...hub.negotiation import NegotiateResponse
from ...messages.ping_message import PingMessage
from ...protocol.base_hub_protocol import BaseHubProtocol
from ...transport.base_reconnection import BaseReconnection
from ...transport.base_transport import TransportState
from ...transport.sockets.utils import create_ssl_context
from ..hub.aio_negotiation import AsyncNegotiationHandler
from ..utils import call_callback

# Bounds for the different connection stages.
AIO_CONNECT_TIMEOUT = 30
AIO_CLOSE_TIMEOUT = 10


class AIOBaseTransport(object):
    connection_alive: bool = False

    def __init__(
            self,
            url: str = None,
            connection_id: str = None,
            is_binary: bool = False,
            skip_negotiation: bool = False,
            token: Optional[str] = None,
            headers: Optional[Dict] = None,
            proxies: Optional[Dict] = None,
            ssl_context: ssl.SSLContext = None,
            enable_trace: bool = False,
            on_open: Callable = None,
            on_close: Callable = None,
            on_reconnect: Callable = None,
            protocol: BaseHubProtocol = None,
            reconnection_handler: BaseReconnection = None,
            on_message: Callable = None):
        self.url = url
        self.is_binary = is_binary
        self.headers = headers
        self.token = token
        self.enable_trace = enable_trace
        self.skip_negotiation = skip_negotiation
        self.ssl_context = ssl_context\
            if ssl_context is not None else\
            create_ssl_context(True)
        self.connection_id = connection_id
        self.proxies = proxies
        self.protocol = protocol

        self.logger = Helpers.get_logger()

        self._on_message = on_message
        self._on_open = on_open
        self._on_close = on_close
        self._on_reconnect = on_reconnect

        self.state = TransportState.disconnected
        self.handshake_received = False
        self.reconnection_handler = reconnection_handler
        self._client = None
        self.manually_closing = False

        self._state_condition = asyncio.Condition()
        self._reconnect_lock = asyncio.Lock()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_pending = False
        self._keepalive_task: Optional[asyncio.Task] = None
        self.keep_alive_interval = getattr(self, "keep_alive_interval", 15)
        self.last_message = time.time()

    async def _set_state(self, new_state: TransportState):
        if new_state == self.state:
            return

        old_state = self.state

        async with self._state_condition:
            self.state = new_state
            self._state_condition.notify_all()

        self.logger.debug(
            f"Transport state changed: {old_state.name} → {new_state.name}")

        was_connecting = old_state == TransportState.connecting
        was_connected = old_state == TransportState.connected
        was_reconnecting = old_state == TransportState.reconnecting

        if was_connecting and self.is_connected():
            await call_callback(self._on_open)
        elif (was_connected or was_reconnecting)\
                and self.is_disconnected():
            await call_callback(self._on_close)
        elif was_reconnecting and self.is_connected():
            await call_callback(self._on_reconnect)

    def is_connected(self):
        return self.state == TransportState.connected

    def is_connecting(self):  # pragma: no cover
        return self.state == TransportState.connecting

    def is_reconnecting(self):
        return self.state == TransportState.reconnecting

    def is_disconnected(self):
        return self.state == TransportState.disconnected

    def is_trace_enabled(self) -> bool:
        return self._client.is_trace_enabled()

    def is_running(self):
        return self.state != TransportState.disconnected

    async def wait_until(
            self,
            predicate: Callable[[], bool],
            timeout: Optional[float] = None) -> None:
        """Waits until predicate() is true.

        The predicate is re-evaluated on every state change; unlike
        wait_until_state it can accept several target states.
        """
        async def _wait():
            async with self._state_condition:
                while not predicate():
                    await self._state_condition.wait()

        await asyncio.wait_for(_wait(), timeout=timeout)

    async def wait_until_state(
            self,
            state: TransportState,
            timeout: Optional[float] = None) -> None:
        await self.wait_until(lambda: self.state == state, timeout=timeout)

    async def negotiate(self) -> NegotiateResponse:
        handler = AsyncNegotiationHandler(
            self.url,
            self.headers,
            self.proxies,
            self.ssl_context,
            self.skip_negotiation)

        self.url, self.headers, response = await handler.negotiate()
        self.connection_id = response.get_id()

        return response

    def create_client(self):  # pragma: no cover
        raise NotImplementedError()

    async def start(self, reconnection: bool = False):
        if not reconnection:
            self.manually_closing = False
            if self.reconnection_handler is not None:
                self.reconnection_handler.reset()

        if reconnection:
            await self.negotiate()
            await self._set_state(TransportState.reconnecting)
        else:
            await self._set_state(TransportState.connecting)

        self.logger.debug("start url:" + self.url)

        self._client = self.create_client()

        try:
            await asyncio.wait_for(
                self._client.connect(), timeout=AIO_CONNECT_TIMEOUT)
        except BaseException:
            with contextlib.suppress(Exception):
                await self._client.dispose()
            raise

        return True

    async def dispose(self):
        await self._stop_keepalive()

        if self._client is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(
                    self._client.close(), timeout=AIO_CLOSE_TIMEOUT)

    async def stop(self):
        if self.is_disconnected():
            return

        self.manually_closing = True
        self.handshake_received = False

        if self.reconnection_handler is not None:
            self.reconnection_handler.reconnecting = False

        try:
            await self._stop_reconnect()
            await self.dispose()
        finally:
            await self._set_state(TransportState.disconnected)

    async def _stop_reconnect(self):
        task = self._reconnect_task
        self._reconnect_task = None
        self._reconnect_pending = False

        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def on_socket_error(self, error: Exception):  # pragma: no cover
        self.logger.error(traceback.format_exc(10, True))
        self.logger.error("{0} {1}".format(self, error))
        self.logger.error("{0} {1}".format(error, type(error)))
        await self._set_state(TransportState.disconnected)

    def _start_keepalive(self):
        if self._keepalive_task is not None\
                and not self._keepalive_task.done():
            return

        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _stop_keepalive(self):
        task = self._keepalive_task
        self._keepalive_task = None

        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _keepalive_loop(self):
        try:
            while self.is_running():
                await asyncio.sleep(min(1, self.keep_alive_interval))

                if time.time() - self.last_message\
                        > self.keep_alive_interval:
                    try:
                        await self.ping_function()
                    except asyncio.CancelledError:
                        raise
                    except Exception as error:
                        self.logger.error(
                            f"Keep alive ping failed: {error}")
                    self.last_message = time.time()
        except asyncio.CancelledError:
            raise
        except Exception as error:  # pragma: no cover
            self.logger.error(f"Keep alive loop error: {error}")

    async def handle_reconnect(self) -> bool:
        if self.manually_closing or self.reconnection_handler is None:
            return False

        if self._client is None or not self._client.is_connection_closed():
            return False

        async with self._reconnect_lock:
            task = self._reconnect_task
            loop_alive = task is not None and not task.done()

            if loop_alive and self.is_reconnecting():
                return True

            self.reconnection_handler.reconnecting = True

        # State callbacks run without the reconnection lock: user code
        # must not be able to deadlock a reconnect.
        await self._set_state(TransportState.reconnecting)

        async with self._reconnect_lock:
            if self._reconnect_task is not None\
                    and not self._reconnect_task.done():
                self._reconnect_pending = True
                return True

            self._reconnect_pending = False
            self._reconnect_task = asyncio.create_task(
                self._reconnect_loop())

        return True

    async def _dispose_current_client(self):
        if self._client is None:  # pragma: no cover
            return

        try:
            await self._client.dispose()
        except Exception as error:  # pragma: no cover
            self.logger.debug(f"Error disposing old client: {error}")

    async def _reconnect_loop(self):
        try:
            while not self.manually_closing:
                await self._dispose_current_client()

                try:
                    sleep_time = self.reconnection_handler.next()
                except ValueError as error:
                    self.logger.error(f"Reconnection failed: {error}")
                    self.reconnection_handler.reconnecting = False
                    await self._stop_keepalive()
                    await self._set_state(TransportState.disconnected)
                    return

                if self.manually_closing:  # pragma: no cover
                    return

                await asyncio.sleep(sleep_time)

                if self.manually_closing:  # pragma: no cover
                    return

                try:
                    await self.start(reconnection=True)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self.logger.warning(
                        f"Reconnection attempt failed: {error}")
                    continue

                async with self._reconnect_lock:
                    pending = self._reconnect_pending
                    self._reconnect_pending = False

                if pending or self.is_disconnected():
                    continue

                return
        finally:
            async with self._reconnect_lock:
                if self._reconnect_task is asyncio.current_task():
                    self._reconnect_task = None
                    self._reconnect_pending = False

    async def send_handshake(self):
        msg = self.protocol.handshake_message()
        self.handshake_received = False
        await self.send(msg)

    async def send(self, message, on_invocation=None):  # pragma: no cover
        raise NotImplementedError()

    async def ping(self):
        await self.send(PingMessage())
