import unittest
from unittest.mock import Mock

from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.transport.base_transport import TransportState
from signalrcore.transport.long_polling.long_polling_transport import\
    LongPollingTransport
from signalrcore.transport.sse.sse_transport import SSETransport
from signalrcore.transport.websockets.websocket_transport import\
    WebsocketTransport


TRANSPORTS = (WebsocketTransport, SSETransport, LongPollingTransport)


class HandshakeStateTest(unittest.TestCase):
    def build(self, transport_cls, opened):
        transport = transport_cls(
            protocol=JsonHubProtocol(),
            on_open=lambda: opened.append(True),
            on_close=lambda: None)
        # Prevent the keep alive thread from being spawned.
        transport.connection_checker.running = True
        transport._client = Mock()
        transport._set_state(TransportState.connecting)
        return transport

    def test_successful_handshake_connects(self):
        for transport_cls in TRANSPORTS:
            with self.subTest(transport=transport_cls.__name__):
                opened = []
                transport = self.build(transport_cls, opened)
                try:
                    messages = transport.on_message(None, "{}\x1e")

                    self.assertEqual(messages, [])
                    self.assertTrue(transport.handshake_received)
                    self.assertTrue(transport.is_connected())
                    self.assertEqual(opened, [True])
                finally:
                    transport.connection_checker.stop()

    def test_rejected_handshake_is_not_connected(self):
        for transport_cls in TRANSPORTS:
            with self.subTest(transport=transport_cls.__name__):
                opened = []
                transport = self.build(transport_cls, opened)
                try:
                    messages = transport.on_message(
                        None, '{"error": "bad handshake"}\x1e')

                    self.assertEqual(messages, [])
                    self.assertFalse(transport.handshake_received)
                    self.assertFalse(transport.is_connected())
                    self.assertEqual(
                        transport.state, TransportState.disconnected)
                    self.assertEqual(opened, [])
                finally:
                    transport.connection_checker.stop()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
