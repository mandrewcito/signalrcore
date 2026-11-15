import asyncio

from ...aio_base_test_case import AIOConnectionBaseTestCase


class TestAIOStreamMethod(AIOConnectionBaseTestCase):
    count = 10
    interval = 100

    async def run_stream(self):
        items = list(range(self.count))
        received = []
        errors = []
        completed = asyncio.Event()

        async def on_next(item):
            await asyncio.sleep(0)
            received.append(item)

        async def on_complete(_):
            completed.set()

        async def on_error(error):
            errors.append(error)
            completed.set()

        stream = await self.connection.stream(
            "Counter", [len(items), self.interval])

        stream.subscribe({
            "next": on_next,
            "complete": on_complete,
            "error": on_error
        })

        await asyncio.wait_for(completed.wait(), timeout=30)

        self.assertEqual(errors, [])
        self.assertEqual(received, items)

    async def test_stream(self):
        await self.run_stream()

    async def test_stream_sync_callbacks(self):
        items = list(range(self.count))
        received = []
        completed = asyncio.Event()

        def on_next(item):
            received.append(item)

        def on_complete(_):
            completed.set()

        def on_error(error):
            completed.set()

        stream = await self.connection.stream(
            "Counter", [len(items), self.interval])

        stream.subscribe({
            "next": on_next,
            "complete": on_complete,
            "error": on_error
        })

        await asyncio.wait_for(completed.wait(), timeout=30)

        self.assertEqual(received, items)

    async def test_stream_subscribe_validation(self):
        stream = await self.connection.stream("Counter", [1, 100])

        with self.assertRaises(TypeError):
            stream.subscribe(None)

        with self.assertRaises(TypeError):
            stream.subscribe([])

        with self.assertRaises(KeyError):
            stream.subscribe({"next": lambda _: None})

        with self.assertRaises(ValueError):
            stream.subscribe({
                "next": "",
                "complete": 1,
                "error": []
            })


class TestAIOStreamSseMethod(TestAIOStreamMethod):
    async def get_connection(self, **kwargs):
        return await super().get_connection_sse(**kwargs)


class TestAIOStreamLongPollingMethod(TestAIOStreamMethod):
    async def get_connection(self, **kwargs):
        return await super().get_connection_long_polling(**kwargs)
