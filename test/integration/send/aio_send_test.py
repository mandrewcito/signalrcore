import asyncio

from ...aio_base_test_case import AIOConnectionBaseTestCase


class AIOSendTests(AIOConnectionBaseTestCase):
    async def test_aio_send(self):
        identifier = self.get_random_id()
        received = asyncio.Event()

        def release(msg):
            if identifier in msg[1]:
                received.set()

        self.connection.on("ReceiveMessage", release)
        message = "new message {0}".format(identifier)
        username = "mandrewcito"

        await self.connection.send("SendMessage", [username, message])

        await asyncio.wait_for(received.wait(), timeout=10)

    async def test_aio_send_async_callback(self):
        identifier = self.get_random_id()
        received = asyncio.Event()

        async def release(msg):
            await asyncio.sleep(0)
            if identifier in msg[1]:
                received.set()

        self.connection.on("ReceiveMessage", release)
        message = "new message {0}".format(identifier)

        await self.connection.send("SendMessage", ["mandrewcito", message])

        await asyncio.wait_for(received.wait(), timeout=10)

    async def test_aio_send_invoke_callback(self):
        completed = asyncio.Event()
        completion = []

        async def on_invocation(message):
            completion.append(message)
            completed.set()

        result = await self.connection.invoke(
            "SendMessage",
            ["mandrewcito", "new message {0}".format(self.get_random_id())],
            on_invocation)

        self.assertIsNotNone(result.invocation_id)

        await asyncio.wait_for(completed.wait(), timeout=10)
        self.assertEqual(completion[0].invocation_id, result.invocation_id)


class AIOSendSseTests(AIOSendTests):
    async def get_connection(self, **kwargs):
        return await super().get_connection_sse(**kwargs)


class AIOSendLongPollingTests(AIOSendTests):
    async def get_connection(self, **kwargs):
        return await super().get_connection_long_polling(**kwargs)
