import logging
import sys
import unittest
import uuid

from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder
from signalrcore.aio.hub.aio_base_hub_connection import AIOBaseHubConnection
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
from signalrcore.types import HttpTransportType

from .base_test_case import Urls


class AIOBaseTestCase(unittest.IsolatedAsyncioTestCase):
    server_url = Urls.server_url_ssl

    def get_random_id(self) -> str:
        return str(uuid.uuid4())

    def is_debug(self) -> bool:
        return "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

    def get_log_level(self):
        return logging.DEBUG\
            if self.is_debug() else logging.ERROR

    def build_connection(
            self,
            url: str = None,
            options: dict = None,
            reconnection: bool = True,
            msgpack: bool = False,
            transport: HttpTransportType = None,
            reconnect_interval: float = 1,
            max_attempts: int = 5) -> AIOBaseHubConnection:
        """Builds an asyncio hub connection.

        Args:
            url: hub url, defaults to the test case server_url
            options: extra with_url options
            reconnection: enable automatic raw reconnection
            msgpack: use the messagepack protocol
            transport: preferred transport
            reconnect_interval: seconds between reconnection attempts
            max_attempts: reconnection attempts before giving up
        """
        if options is None:
            options = {"verify_ssl": False}
        else:
            options = dict(options)

        if transport is not None:
            options["transport"] = transport

        builder = AIOHubConnectionBuilder()\
            .with_url(url or self.server_url, options=options)\
            .configure_logging(
                self.get_log_level(),
                socket_trace=self.is_debug())

        if reconnection:
            builder.with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": reconnect_interval,
                "max_attempts": max_attempts
            })

        if msgpack:
            builder.with_hub_protocol(MessagePackHubProtocol())

        return builder.build()

    async def start_connection(self, **kwargs) -> AIOBaseHubConnection:
        connection = self.build_connection(**kwargs)
        await connection.start()
        return connection


class AIOConnectionBaseTestCase(AIOBaseTestCase):
    server_url = Urls.server_url_ssl
    connection: AIOBaseHubConnection

    async def _connect(
            self,
            options: dict = None,
            reconnection: bool = True,
            msgpack: bool = False,
            transport: HttpTransportType = None,
            url: str = None) -> AIOBaseHubConnection:
        return await self.start_connection(
            url=url,
            options=options,
            reconnection=reconnection,
            msgpack=msgpack,
            transport=transport)

    async def get_connection(
            self,
            options: dict = None,
            reconnection: bool = True,
            msgpack: bool = False,
            transport: HttpTransportType = None,
            url: str = None) -> AIOBaseHubConnection:
        return await self._connect(
            options=options,
            reconnection=reconnection,
            msgpack=msgpack,
            transport=transport,
            url=url)

    async def get_connection_sse(
            self,
            msgpack: bool = False,
            reconnection: bool = True,
            options: dict = None,
            url: str = None) -> AIOBaseHubConnection:
        return await self._connect(
            url=url or Urls.ws_to_http(self.server_url),
            options=options,
            reconnection=reconnection,
            msgpack=msgpack,
            transport=HttpTransportType.server_sent_events)

    async def get_connection_long_polling(
            self,
            msgpack: bool = False,
            reconnection: bool = True,
            options: dict = None,
            url: str = None) -> AIOBaseHubConnection:
        return await self._connect(
            url=url or Urls.ws_to_http(self.server_url),
            options=options,
            reconnection=reconnection,
            msgpack=msgpack,
            transport=HttpTransportType.long_polling)

    async def dispose(self):
        if getattr(self, "connection", None) is not None:
            await self.connection.stop()
            del self.connection

    async def asyncSetUp(self):
        self.connection = await self.get_connection()

    async def asyncTearDown(self):
        await self.dispose()
