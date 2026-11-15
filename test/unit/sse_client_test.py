import unittest
from unittest.mock import Mock

from signalrcore.transport.sse.sse_client import SSEClient


class SSEDisposeTest(unittest.TestCase):
    def setUp(self):
        self.client = SSEClient(url="http://localhost/chat")
        self.client.recv_thread = None

    def test_sets_linger_and_closes_socket(self):
        self.client.sock = Mock()

        self.client.dispose()

        self.client.sock.setsockopt.assert_called_once()
        self.client.sock.close.assert_called_once()

    def test_closes_socket_when_setsockopt_fails(self):
        self.client.sock = Mock()
        self.client.sock.setsockopt.side_effect = OSError("no linger")

        self.client.dispose()

        self.client.sock.close.assert_called_once()

    def test_recv_thread_is_joined_when_setsockopt_fails(self):
        thread = Mock()
        self.client.sock = Mock()
        self.client.sock.setsockopt.side_effect = OSError("no linger")
        self.client.recv_thread = thread

        self.client.dispose()

        thread.join.assert_called_once()

    def test_dispose_before_connect_does_not_raise(self):
        self.client.dispose()

    def test_dispose_is_idempotent(self):
        self.client.sock = Mock()

        self.client.dispose()
        self.client.dispose()

        self.assertEqual(self.client.sock.close.call_count, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
