import threading
import logging
import uuid
import requests
from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
from ...aio_base_test_case import AIOConnectionBaseTestCase, Urls
from ...base_test_case import LOCK_TIMEOUT


class TestAIOSendAuthMethod(AIOConnectionBaseTestCase):
    server_url = Urls.server_url_ssl_auth
    login_url = Urls.login_url_ssl
    email = "test"
    password = "test"
    received = False
    message = None
    _lock = None

    def login(self):
        response = requests.post(
            self.login_url,
            json={
                "username": self.email,
                "password": self.password
                },
            verify=False)
        return response.json()["token"]

    async def get_connection(self, msgpack=False):
        builder = AIOHubConnectionBuilder()\
            .with_url(
                self.server_url,
                options={
                    "verify_ssl": False,
                    "access_token_factory": self.login,
                    "headers": {
                        "mycustomheader": "mycustomheadervalue"
                    }
                })

        if msgpack:
            builder.with_hub_protocol(MessagePackHubProtocol())

        builder.configure_logging(logging.WARNING)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })
        connection = builder.build()
        connection.on("ReceiveMessage", self.receive_message)
        await connection.start()
        return connection

    def receive_message(self, args):
        self._lock.release()
        self.assertEqual(args[0], self.message)

    async def test_send(self):
        self._lock = threading.Lock()
        self.message = "new message {0}".format(uuid.uuid4())
        self.username = "mandrewcito"
        self.assertTrue(self._lock.acquire(timeout=LOCK_TIMEOUT))
        await self.connection.send("SendMessage", [self.message])
        self.assertTrue(self._lock.acquire(timeout=LOCK_TIMEOUT))
        del self._lock


class TestSendNoSslAuthMethod(TestAIOSendAuthMethod):
    server_url = Urls.server_url_no_ssl_auth
    login_url = Urls.login_url_no_ssl


class TestSendAuthMethodMsgPack(TestAIOSendAuthMethod):
    async def get_connection(self):
        return await super().get_connection(
            msgpack=True)


class TestSendNoSslAuthMethodMsgPack(TestAIOSendAuthMethod):
    server_url = Urls.server_url_no_ssl_auth
    login_url = Urls.login_url_no_ssl
