import unittest
from unittest.mock import Mock

from signalrcore.hub.base_hub_connection import BaseHubConnection
from signalrcore.hub.errors import HubConnectionError
from signalrcore.messages.stream_invocation_message import \
    StreamInvocationMessage


class StreamReadinessTest(unittest.TestCase):
    def setUp(self):
        self.connection = BaseHubConnection(url="http://localhost/hub")

    def test_stream_without_transport_raises(self):
        with self.assertRaises(HubConnectionError):
            self.connection.stream("Counter", [1, 2])

        self.assertEqual(len(self.connection.stream_handlers), 0)

    def test_stream_with_stopped_transport_raises(self):
        self.connection.transport = Mock()
        self.connection.transport.is_running.return_value = False

        with self.assertRaises(HubConnectionError):
            self.connection.stream("Counter", [1, 2])

        self.connection.transport.send.assert_not_called()
        self.assertEqual(len(self.connection.stream_handlers), 0)

    def test_stream_sends_invocation_when_running(self):
        self.connection.transport = Mock()
        self.connection.transport.is_running.return_value = True

        handler = self.connection.stream("Counter", [1, 2])

        self.connection.transport.send.assert_called_once()
        message = self.connection.transport.send.call_args[0][0]
        self.assertIsInstance(message, StreamInvocationMessage)
        self.assertEqual(message.target, "Counter")
        self.assertEqual(message.arguments, [1, 2])
        self.assertEqual(
            self.connection.stream_handlers[message.invocation_id],
            [handler])
        self.assertEqual(handler.event, "Counter")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
