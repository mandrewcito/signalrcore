import unittest
from unittest.mock import Mock

from signalrcore.messages.completion_message import\
    CompletionClientStreamMessage
from signalrcore.messages.invocation_message import\
    InvocationClientStreamMessage
from signalrcore.messages.stream_item_message import StreamItemMessage
from signalrcore.subject import Subject


class SubjectLockTest(unittest.TestCase):
    def build_subject(self, send=None):
        subject = Subject()
        subject.target = "UploadStream"

        connection = Mock()
        connection.transport.send = send if send is not None else Mock()
        subject.connection = connection
        return subject

    def test_next_releases_lock_when_send_raises(self):
        def send(message):
            raise RuntimeError("send failed")

        subject = self.build_subject(send)

        with self.assertRaises(RuntimeError):
            subject.next("item")

        self.assertFalse(subject.lock.locked())

    def test_start_releases_lock_when_send_raises(self):
        def send(message):
            raise RuntimeError("send failed")

        subject = self.build_subject(send)

        with self.assertRaises(RuntimeError):
            subject.start()

        self.assertFalse(subject.lock.locked())

    def test_complete_releases_lock_when_send_raises(self):
        def send(message):
            raise RuntimeError("send failed")

        subject = self.build_subject(send)

        with self.assertRaises(RuntimeError):
            subject.complete()

        self.assertFalse(subject.lock.locked())

    def test_successful_calls_release_lock(self):
        subject = self.build_subject()

        subject.start()
        subject.next("item")
        subject.complete()

        self.assertFalse(subject.lock.locked())

    def test_sent_messages(self):
        subject = self.build_subject()

        subject.start()
        subject.next("item")
        subject.complete()

        messages = [
            call.args[0]
            for call in subject.connection.transport.send.call_args_list]

        self.assertEqual(len(messages), 3)
        self.assertIsInstance(messages[0], InvocationClientStreamMessage)
        self.assertEqual(messages[0].stream_ids, [subject.invocation_id])
        self.assertEqual(messages[0].target, "UploadStream")
        self.assertIsInstance(messages[1], StreamItemMessage)
        self.assertEqual(messages[1].item, "item")
        self.assertIsInstance(
            messages[2], CompletionClientStreamMessage)

    def test_lock_timeout_raises_timeout_error(self):
        subject = self.build_subject()
        subject._timeout = 0.01
        subject.lock.acquire()

        try:
            with self.assertRaises(TimeoutError):
                subject.next("item")
        finally:
            subject.lock.release()

        self.assertFalse(subject.lock.locked())
        subject.connection.transport.send.assert_not_called()

    def test_unbound_subject_raises_value_error(self):
        subject = Subject()

        with self.assertRaises(ValueError):
            subject.next("item")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
