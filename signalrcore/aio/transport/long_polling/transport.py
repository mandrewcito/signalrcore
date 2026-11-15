import asyncio
import time
from typing import Optional

from ....messages.ping_message import PingMessage
from ....protocol.messagepack_protocol import MessagePackHubProtocol
from ....transport.base_transport import TransportState
from ...utils import call_callback
from ..base_transport import AIOBaseTransport
from .client import (
    AIOLongPollingBaseClient,
    AIOLongPollingBinaryClient,
    AIOLongPollingTextClient,
)


class AIOLongPollingTransport(AIOBaseTransport):
    _client: Optional[AIOLongPollingBaseClient] = None

    def __init__(self, keep_alive_interval=15, **kwargs):
        super().__init__(**kwargs)
        self.keep_alive_interval = keep_alive_interval

        self._client_cls = AIOLongPollingBinaryClient\
            if self.is_binary\
            or type(self.protocol) is MessagePackHubProtocol\
            else AIOLongPollingTextClient

        self.manually_closing = False
        self.connection_alive = False
        self.ping_function = self.connection_check

    async def connection_check(self):
        time_without_messages = time.time() - self.last_message

        self.connection_alive =\
            time_without_messages < self.keep_alive_interval

        if self._client.is_connection_closed()\
                and self.reconnection_handler is None:
            await self._stop_keepalive()
            await self._set_state(TransportState.disconnected)
            return

        if not self._client.is_connection_closed():
            await self.send(PingMessage())

        await self.handle_reconnect()

    def create_client(self) -> AIOLongPollingBaseClient:
        return self._client_cls(
            url=self.url,
            connection_id=self.connection_id,
            headers=self.headers,
            proxies=self.proxies,
            ssl_context=self.ssl_context,
            enable_trace=self.enable_trace,
            on_message=self.on_message,
            on_open=self.on_client_open,
            on_close=self.on_client_close,
            on_error=self.on_client_error)

    async def on_client_error(self, error: Exception):  # pragma: no cover
        self.logger.debug("-- Long Polling error --")
        await super().on_socket_error(error)

    async def on_client_close(self):
        if self.reconnection_handler is not None\
                and not self.is_reconnecting()\
                and not self.manually_closing:
            await self.handle_reconnect()
            return

        self.logger.debug("-- Long Polling close --")
        await self._set_state(TransportState.disconnected)

    async def on_client_open(self):
        self.logger.debug("-- Long Polling open --")
        await self.send_handshake()

    async def evaluate_handshake(self, message):
        self.logger.debug("Evaluating handshake {0}".format(message))

        handshake_response, messages = self.protocol.decode_handshake(
            message)

        self.handshake_received = handshake_response.error is None

        if self.handshake_received:
            await self._set_state(TransportState.connected)

            if self.reconnection_handler is not None:
                self.reconnection_handler.reset()

            self._start_keepalive()
            self.last_message = time.time()
        else:
            self.logger.error(handshake_response.error)
            await self.on_client_error(handshake_response.error)

        return messages

    async def on_message(self, app, raw_message):
        self.logger.debug("Message received {0}".format(raw_message))

        self.last_message = time.time()

        if not self.manually_closing and not self.handshake_received:
            messages = await self.evaluate_handshake(raw_message)

            if not self.handshake_received:
                return []

            if len(messages) > 0:
                return await call_callback(self._on_message, messages)

            return []

        return await call_callback(
            self._on_message,
            self.protocol.parse_messages(raw_message))

    async def send(self, message):
        self.logger.debug("Sending message {0}".format(message))
        try:
            await self._client.send(self.protocol.encode(message))
            self.last_message = time.time()
        except asyncio.CancelledError:
            raise
        except OSError as error:
            self.handshake_received = False
            self.logger.warning("Connection closed {0}".format(error))

            if self.reconnection_handler is None:
                await self._set_state(TransportState.disconnected)
                raise ValueError(str(error))

            await self.handle_reconnect()
