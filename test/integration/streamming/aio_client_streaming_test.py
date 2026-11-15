import asyncio

from signalrcore.aio.subject import AIOSubject

from ...aio_base_test_case import AIOConnectionBaseTestCase


class TestAIOClientStreamMethod(AIOConnectionBaseTestCase):
    async def test_stream(self):
        items = [str(i) for i in range(10)]
        subject = AIOSubject()

        await self.connection.send("UploadStream", subject)

        for item in items:
            await subject.next(item)

        await subject.complete()

        await asyncio.sleep(0.5)
        self.assertTrue(
            self.connection.transport.is_connected(),
            "Server closed the connection while receiving the client stream")


class TestAIOClientStreamSseMethod(TestAIOClientStreamMethod):
    async def get_connection(self, **kwargs):
        return await super().get_connection_sse(**kwargs)


class TestAIOClientStreamLongPollingMethod(TestAIOClientStreamMethod):
    async def get_connection(self, **kwargs):
        return await super().get_connection_long_polling(**kwargs)


class TestAIOClientStreamEcho(AIOConnectionBaseTestCase):
    """Client to server streaming round trip.

    The client uploads a stream, the server collects the items and echoes
    them back to the caller.
    """

    async def test_echo(self):
        items = [str(i) for i in range(5)]
        received = []
        done = asyncio.Event()

        async def on_items(args):
            received.extend(args[0])
            done.set()

        self.connection.on("EchoStreamItems", on_items)

        subject = AIOSubject()
        await self.connection.send("EchoStream", subject)

        for item in items:
            await subject.next(item)

        await subject.complete()

        await asyncio.wait_for(done.wait(), timeout=10)
        self.assertEqual(received, items)


class TestAIOClientStreamEchoMsgPack(TestAIOClientStreamEcho):
    async def get_connection(self, **kwargs):
        kwargs["msgpack"] = True
        return await super().get_connection(**kwargs)
