import unittest

from signalrcore.transport.long_polling.long_polling_client import\
    LongPollingTextClient


class LongPollingClientAppendTest(unittest.TestCase):
    def setUp(self):
        self.client = LongPollingTextClient(url="")

    def test_append_returns_all_complete_messages(self):
        frame = b'{"type":1}\x1e{"type":3}\x1e{"type":6'

        messages = self.client._append(frame)

        self.assertEqual(
            messages,
            [b'{"type":1}', b'{"type":3}'])
        self.assertEqual(self.client._buffer, b'{"type":6')

    def test_append_returns_empty_list_without_complete_messages(self):
        messages = self.client._append(b'{"type":6')

        self.assertEqual(messages, [])
        self.assertEqual(self.client._buffer, b'{"type":6')

    def test_append_joins_partial_frames(self):
        self.assertEqual(self.client._append(b'{"type":1'), [])
        self.assertEqual(
            self.client._append(b'}\x1e'),
            [b'{"type":1}'])
        self.assertEqual(self.client._buffer, b"")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
