import asyncio
import unittest
from unittest.mock import Mock

from signalrcore.aio.hub.aio_base_hub_connection import (
    AIOBaseHubConnection,
)
from signalrcore.aio.subject import AIOSubject
from signalrcore.messages.completion_message import (
    CompletionClientStreamMessage,
)
from signalrcore.messages.invocation_message import (
    InvocationClientStreamMessage,
)
from signalrcore.messages.stream_item_message import StreamItemMessage
from signalrcore.subject import Subject
from signalrcore.transport.base_transport import TransportState


class FakeTransport(object):
    def __init__(self, send=None):
        self.state = TransportState.connected
        self.sent = []
        if send is not None:
            self._send = send

    def is_running(self):
        return True

    async def send(self, message, on_invocation=None):
        await self._send(message)

    async def _send(self, message):
        self.sent.append(message)


class AIOSubjectTest(unittest.IsolatedAsyncioTestCase):
    def build_subject(self, send=None):
        subject = AIOSubject()
        subject.target = "UploadStream"

        connection = Mock()
        connection.transport = FakeTransport(send)
        subject.connection = connection
        return subject

    async def test_next_releases_lock_when_send_raises(self):
        async def send(message):
            raise RuntimeError("send failed")

        subject = self.build_subject(send)

        with self.assertRaises(RuntimeError):
            await subject.next("item")

        self.assertFalse(subject.lock.locked())

    async def test_start_releases_lock_when_send_raises(self):
        async def send(message):
            raise RuntimeError("send failed")

        subject = self.build_subject(send)

        with self.assertRaises(RuntimeError):
            await subject.start()

        self.assertFalse(subject.lock.locked())

    async def test_complete_releases_lock_when_send_raises(self):
        async def send(message):
            raise RuntimeError("send failed")

        subject = self.build_subject(send)

        with self.assertRaises(RuntimeError):
            await subject.complete()

        self.assertFalse(subject.lock.locked())

    async def test_successful_calls_release_lock(self):
        subject = self.build_subject()

        await subject.start()
        await subject.next("item")
        await subject.complete()

        self.assertFalse(subject.lock.locked())

    async def test_sent_messages(self):
        subject = self.build_subject()

        await subject.start()
        await subject.next("item")
        await subject.complete()

        messages = subject.connection.transport.sent

        self.assertEqual(len(messages), 3)
        self.assertIsInstance(messages[0], InvocationClientStreamMessage)
        self.assertEqual(messages[0].stream_ids, [subject.invocation_id])
        self.assertEqual(messages[0].target, "UploadStream")
        self.assertIsInstance(messages[1], StreamItemMessage)
        self.assertEqual(messages[1].item, "item")
        self.assertIsInstance(
            messages[2], CompletionClientStreamMessage)

    async def test_concurrent_sends_keep_order(self):
        events = []

        async def send(message):
            events.append(("start", message))
            await asyncio.sleep(0.01)
            events.append(("end", message))

        subject = self.build_subject(send)

        await asyncio.gather(
            subject.next("first"),
            subject.next("second"))

        items = [message.item for _, message in events]
        self.assertEqual(items, ["first", "first", "second", "second"])
        self.assertEqual(events[0][0], "start")
        self.assertEqual(events[-1][0], "end")

    async def test_lock_timeout_raises_timeout_error(self):
        subject = self.build_subject()
        subject._timeout = 0.01
        await subject.lock.acquire()

        try:
            with self.assertRaises(TimeoutError):
                await subject.next("item")
        finally:
            subject.lock.release()

        self.assertFalse(subject.lock.locked())
        self.assertEqual(subject.connection.transport.sent, [])

    async def test_unbound_subject_raises_value_error(self):
        subject = AIOSubject()

        with self.assertRaises(ValueError):
            await subject.next("item")


class AIOClientStreamingInvokeTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.connection = AIOBaseHubConnection(url="http://localhost/hub")
        self.transport = FakeTransport()
        self.connection.transport = self.transport

    async def test_invoke_starts_client_stream(self):
        subject = AIOSubject()

        result = await self.connection.invoke("UploadStream", subject)

        self.assertIs(result.message, subject)
        self.assertEqual(result.invocation_id, subject.invocation_id)
        self.assertIs(subject.connection, self.connection)
        self.assertEqual(subject.target, "UploadStream")

        self.assertEqual(len(self.transport.sent), 1)
        message = self.transport.sent[0]
        self.assertIsInstance(message, InvocationClientStreamMessage)
        self.assertEqual(message.stream_ids, [subject.invocation_id])
        self.assertEqual(message.target, "UploadStream")

    async def test_invoke_rejects_sync_subject(self):
        subject = Subject()

        with self.assertRaises(TypeError):
            await self.connection.invoke("UploadStream", subject)

        self.assertEqual(self.transport.sent, [])

    async def test_client_stream_can_send_items_after_invoke(self):
        subject = AIOSubject()

        await self.connection.invoke("UploadStream", subject)
        await subject.next("item")
        await subject.complete()

        self.assertIsInstance(self.transport.sent[1], StreamItemMessage)
        self.assertEqual(self.transport.sent[1].item, "item")
        self.assertIsInstance(
            self.transport.sent[2], CompletionClientStreamMessage)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
