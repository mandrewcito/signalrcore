import asyncio
import uuid

import requests

from ...aio_base_test_case import AIOConnectionBaseTestCase, Urls
from ...base_test_case import LOCK_TIMEOUT


class TestAIOSendAuthMethod(AIOConnectionBaseTestCase):
    server_url = Urls.server_url_ssl_auth
    login_url = Urls.login_url_ssl
    email = "test"
    password = "test"

    def login(self):
        response = requests.post(
            self.login_url,
            json={
                "username": self.email,
                "password": self.password
                },
            verify=False)
        return response.json()["token"]

    async def async_login(self):
        return await asyncio.to_thread(self.login)

    def get_auth_function(self):
        return self.login

    async def get_connection(self, msgpack=False):
        options = {
            "verify_ssl": False,
            "access_token_factory": self.get_auth_function(),
            "headers": {
                "mycustomheader": "mycustomheadervalue"
            }
        }

        return await self.start_connection(
            url=self.server_url,
            options=options,
            reconnection=True,
            msgpack=msgpack)

    async def test_send(self):
        received = asyncio.Event()
        message = "new message {0}".format(uuid.uuid4())

        async def on_message(args):
            if args[0] == message:
                received.set()

        self.connection.on("ReceiveMessage", on_message)

        await self.connection.send("SendMessage", [message])
        await asyncio.wait_for(received.wait(), timeout=LOCK_TIMEOUT)

        self.assertTrue(
            self.connection.headers["Authorization"].startswith("Bearer "))


class TestAIOSendAuthAsyncFactory(TestAIOSendAuthMethod):
    def get_auth_function(self):
        return self.async_login


class TestAIOSendNoSslAuthMethod(TestAIOSendAuthMethod):
    server_url = Urls.server_url_no_ssl_auth
    login_url = Urls.login_url_no_ssl


class TestAIOSendAuthMethodMsgPack(TestAIOSendAuthMethod):
    async def get_connection(self, msgpack=False):
        return await super().get_connection(msgpack=True)


class TestAIOSendNoSslAuthMethodMsgPack(TestAIOSendNoSslAuthMethod):
    async def get_connection(self, msgpack=False):
        return await super().get_connection(msgpack=True)
