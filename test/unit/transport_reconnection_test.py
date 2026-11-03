import unittest
from unittest.mock import Mock

from signalrcore.messages.ping_message import PingMessage
from signalrcore.transport.reconnection import RawReconnectionHandler
from signalrcore.transport.websockets.websocket_transport import\
    WebsocketTransport


class WebsocketTransportDeferredReconnectTest(unittest.TestCase):
    def setUp(self):
        self.transport = WebsocketTransport(
            keep_alive_interval=15,
            reconnection_handler=RawReconnectionHandler(
                sleep_time=0.01,
                max_attempts=3))
        self.transport.send = Mock()

    def test_connection_alive_is_initialized(self):
        self.assertFalse(self.transport.connection_alive)

    def test_deferred_reconnect_sends_ping_when_connection_not_alive(self):
        self.transport.deferred_reconnect(0)

        self.transport.send.assert_called_once()
        message = self.transport.send.call_args[0][0]
        self.assertIsInstance(message, PingMessage)

    def test_deferred_reconnect_skips_ping_when_connection_alive(self):
        self.transport.connection_alive = True

        self.transport.deferred_reconnect(0)

        self.transport.send.assert_not_called()

    def test_deferred_reconnect_skips_ping_when_checker_is_running(self):
        self.transport.connection_checker.running = True

        self.transport.deferred_reconnect(0)

        self.transport.send.assert_not_called()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
