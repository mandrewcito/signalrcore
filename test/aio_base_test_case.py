import unittest
import uuid
import sys
import logging
from .base_test_case import Urls
from signalrcore.aio.aio_hub_connection_builder import\
    AIOBaseHubConnection, AIOHubConnectionBuilder


class AIOBaseTestCase(unittest.IsolatedAsyncioTestCase):
    server_url = Urls.server_url_ssl

    def get_random_id(self) -> str:
        return str(uuid.uuid4())

    def is_debug(self) -> bool:
        return "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

    def get_log_level(self):
        return logging.DEBUG\
            if self.is_debug() else logging.ERROR

    def tearDown(self):
        return super().tearDown()

    def setUp(self):
        return super().setUp()


class AIOConnectionBaseTestCase(AIOBaseTestCase):
    server_url = Urls.server_url_ssl
    connection: AIOBaseHubConnection

    async def get_connection(self, options={"verify_ssl": False})\
            -> AIOBaseHubConnection:
        builder = AIOHubConnectionBuilder()\
            .with_url(self.server_url, options=options)\
            .configure_logging(
                self.get_log_level(),
                socket_trace=self.is_debug())\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })

        hub = builder.build()

        await hub.start()

        return hub

    async def dispose(self):
        if self.connection is not None:
            await self.connection.stop()
            del self.connection

    async def asyncTearDown(self):
        await self.dispose()

    async def asyncSetUp(self):
        connection = await self.get_connection()
        self.connection = connection
