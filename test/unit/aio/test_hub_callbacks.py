import asyncio
import unittest

from signalrcore.aio.hub.aio_base_hub_connection import (
    AIOBaseHubConnection,
)
from signalrcore.aio.hub.handlers import (
    AIOInvocationHandler,
    AIOStreamHandler,
)
from signalrcore.messages.cancel_invocation_message import (
    CancelInvocationMessage,
)
from signalrcore.messages.close_message import CloseMessage
from signalrcore.messages.completion_message import CompletionMessage
from signalrcore.messages.invocation_message import InvocationMessage
from signalrcore.messages.stream_item_message import StreamItemMessage
from signalrcore.transport.base_transport import TransportState


class FakeTransport(object):
    def __init__(self):
        self.state = TransportState.connected
        self.disposed = False

    def is_running(self):
        return True

    async def dispose(self):
        self.disposed = True


class AIOEventCallbackTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connection = AIOBaseHubConnection(url="http://localhost/hub")
        self.connection.transport = FakeTransport()
        self.events = []

    async def test_sync_event_callback(self):
        self.connection.on(
            "ReceiveMessage",
            lambda arguments: self.events.append(arguments))

        await self.connection.on_message(
            [InvocationMessage("id", "ReceiveMessage", ["hello"])])

        self.assertEqual(self.events, [["hello"]])

    async def test_async_event_callback_is_awaited(self):
        async def callback(arguments):
            await asyncio.sleep(0)
            self.events.append(arguments)

        self.connection.on("ReceiveMessage", callback)

        await self.connection.on_message(
            [InvocationMessage("id", "ReceiveMessage", ["hello"])])

        self.assertEqual(self.events, [["hello"]])

    async def test_async_callbacks_keep_message_order(self):
        async def first(arguments):
            await asyncio.sleep(0.01)
            self.events.append(("first", arguments))

        async def second(arguments):
            self.events.append(("second", arguments))

        self.connection.on("ReceiveMessage", first)
        self.connection.on("ReceiveMessage", second)

        await self.connection.on_message(
            [InvocationMessage("id", "ReceiveMessage", ["hello"])])

        self.assertEqual(
            self.events,
            [("first", ["hello"]), ("second", ["hello"])])


class AIOStreamCallbackTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connection = AIOBaseHubConnection(url="http://localhost/hub")
        self.connection.transport = FakeTransport()
        self.events = []

    def add_stream_handler(self):
        handler = AIOStreamHandler("Counter", "invocation-id")
        handler.subscribe({
            "next": self.on_next,
            "complete": self.on_complete,
            "error": self.on_error,
        })
        self.connection.stream_handlers["invocation-id"].append(handler)
        return handler

    async def on_next(self, item):
        await asyncio.sleep(0)
        self.events.append(("next", item))

    async def on_complete(self, message):
        await asyncio.sleep(0)
        self.events.append(("complete", message))

    async def on_error(self, message):
        await asyncio.sleep(0)
        self.events.append(("error", message))

    async def test_stream_item_callback_is_awaited(self):
        self.add_stream_handler()

        await self.connection.on_message(
            [StreamItemMessage("invocation-id", 1)])

        self.assertEqual(self.events, [("next", 1)])

    async def test_stream_complete_callback_is_awaited(self):
        self.add_stream_handler()
        message = CompletionMessage("invocation-id", None, None)

        await self.connection.on_message([message])

        self.assertEqual(self.events, [("complete", message)])
        self.assertNotIn("invocation-id", self.connection.stream_handlers)

    async def test_stream_error_callback_is_awaited(self):
        self.add_stream_handler()
        self.connection.on_error(
            lambda message: self.events.append(("global", message)))
        message = CompletionMessage("invocation-id", None, "boom")

        await self.connection.on_message([message])

        self.assertEqual(self.events, [("error", message)])
        self.assertNotIn("invocation-id", self.connection.stream_handlers)

    async def test_cancel_invocation_calls_stream_error(self):
        self.add_stream_handler()

        message = CancelInvocationMessage("invocation-id")

        await self.connection.on_message([message])

        self.assertEqual(self.events, [("error", message)])
        self.assertNotIn("invocation-id", self.connection.stream_handlers)

    async def test_sync_stream_callbacks_are_supported(self):
        handler = AIOStreamHandler("Counter", "invocation-id")
        handler.subscribe({
            "next": lambda item: self.events.append(("next", item)),
            "complete": lambda message: self.events.append(("complete",)),
            "error": lambda message: self.events.append(("error",)),
        })
        self.connection.stream_handlers["invocation-id"].append(handler)

        await self.connection.on_message(
            [StreamItemMessage("invocation-id", 2)])

        self.assertEqual(self.events, [("next", 2)])


class AIOInvocationCallbackTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connection = AIOBaseHubConnection(url="http://localhost/hub")
        self.connection.transport = FakeTransport()
        self.events = []

    async def test_invocation_completion_is_awaited(self):
        async def completed(message):
            await asyncio.sleep(0)
            self.events.append(message)

        self.connection.stream_handlers["invocation-id"].append(
            AIOInvocationHandler("invocation-id", completed))

        message = CompletionMessage("invocation-id", "result", None)
        await self.connection.on_message([message])

        self.assertEqual(self.events, [message])

    async def test_invocation_error_falls_back_to_global_error(self):
        async def global_error(message):
            await asyncio.sleep(0)
            self.events.append(("global", message))

        self.connection.stream_handlers["invocation-id"].append(
            AIOInvocationHandler(
                "invocation-id", lambda message: self.events.append(
                    ("invoke", message))))
        self.connection.on_error(global_error)

        message = CompletionMessage("invocation-id", None, "boom")
        await self.connection.on_message([message])

        self.assertEqual(self.events, [("global", message)])
        self.assertNotIn("invocation-id", self.connection.stream_handlers)


class AIOCloseMessageTest(unittest.IsolatedAsyncioTestCase):
    async def test_close_message_disposes_transport(self):
        connection = AIOBaseHubConnection(url="http://localhost/hub")
        transport = FakeTransport()
        connection.transport = transport

        await connection.on_message(
            [CloseMessage(error=None, allow_reconnect=None)])

        self.assertTrue(transport.disposed)
