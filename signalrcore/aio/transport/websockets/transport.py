import asyncio
import time
from typing import Optional

from ....messages.ping_message import PingMessage
from ....protocol.messagepack_protocol import MessagePackHubProtocol
from ....transport.base_transport import TransportState
from ....transport.sockets.errors import SocketClosedError
from ...utils import call_callback
from ..base_transport import AIOBaseTransport
from .client import AIOWebSocketClient


class AIOWebsocketTransport(AIOBaseTransport):
    _client: Optional[AIOWebSocketClient] = None

    def __init__(self, keep_alive_interval=15, **kwargs):
        super().__init__(**kwargs)
        self.handshake_received = False
        self.connection_alive = False
        self.keep_alive_interval = keep_alive_interval
        self.ping_function = self.send_ping

    def create_client(self) -> AIOWebSocketClient:
        return AIOWebSocketClient(
            url=self.url,
            connection_id=self.connection_id,
            headers=self.headers,
            proxies=self.proxies,
            is_binary=type(self.protocol) is MessagePackHubProtocol,
            ssl_context=self.ssl_context,
            enable_trace=self.enable_trace,
            on_message=self.on_message,
            on_error=self.on_socket_error,
            on_close=self.on_socket_close,
            on_open=self.on_socket_open)

    async def evaluate_handshake(self, message):
        self.logger.debug("Evaluating handshake {0}".format(message))
        msg, messages = self.protocol.decode_handshake(message)

        if msg.error is None or msg.error == "":
            self.handshake_received = True

            if self.reconnection_handler is not None:
                self.reconnection_handler.reset()

            await self._set_state(TransportState.connected)

            if self.reconnection_handler is not None:
                self._start_keepalive()
        else:
            self.logger.error(msg.error)
            await self.on_socket_error(msg.error)
            await self.stop()

        return messages

    async def on_socket_error(self, error: Exception):  # pragma: no cover
        self.logger.debug("-- web socket error --")
        await super().on_socket_error(error)

    async def on_socket_close(self):
        if not self.manually_closing\
                and self.reconnection_handler is not None\
                and not self.is_reconnecting():
            await self.handle_reconnect()
            return

        await self._set_state(TransportState.disconnected)

    async def on_socket_open(self):
        self.logger.debug("-- web socket open --")
        await self.send_handshake()

    async def on_message(self, app, raw_message):
        self.logger.debug("Message received {0}".format(raw_message))
        self.last_message = time.time()

        if not self.handshake_received:
            messages = await self.evaluate_handshake(raw_message)

            if not self.handshake_received:
                return []

            if len(messages) > 0:
                return await call_callback(self._on_message, messages)

            return []

        return await call_callback(
            self._on_message,
            self.protocol.parse_messages(raw_message))

    async def send_ping(self):
        await self.send(PingMessage())

    async def send(self, message):
        self.logger.debug("Sending message {0}".format(message))
        try:
            await self._client.send(
                self.protocol.encode(message),
                opcode=0x2
                if type(self.protocol) is MessagePackHubProtocol else
                0x1)
            self.last_message = time.time()
        except asyncio.CancelledError:
            raise
        except (OSError, SocketClosedError) as error:  # pragma: no cover
            self.handshake_received = False
            self.logger.warning("Connection closed {0}".format(error))

            if self.reconnection_handler is None:
                await self._set_state(TransportState.disconnected)
                raise ValueError(str(error))

            await self.handle_reconnect()
