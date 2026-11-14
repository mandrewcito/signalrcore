import threading
import unittest
from unittest.mock import Mock

from signalrcore.messages.ping_message import PingMessage
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.transport.long_polling.long_polling_transport import\
    LongPollingTransport
from signalrcore.transport.reconnection import RawReconnectionHandler
from signalrcore.transport.sse.sse_transport import SSETransport
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


class WebsocketTransportReconnectLoopTest(unittest.TestCase):
    def build_transport(self, handler):
        return WebsocketTransport(
            keep_alive_interval=15,
            protocol=JsonHubProtocol(),
            reconnection_handler=handler,
            on_open=lambda: None,
            on_close=lambda: None,
            on_reconnect=lambda: None)

    def test_retries_until_max_attempts_then_gives_up(self):
        handler = RawReconnectionHandler(sleep_time=0.001, max_attempts=2)
        transport = self.build_transport(handler)

        client = Mock()
        client.is_connection_closed.return_value = True
        transport._client = client

        attempts = []

        def start(reconnection=False):
            attempts.append(reconnection)
            raise OSError("server unavailable")

        transport.start = start

        self.assertTrue(transport.handle_reconnect())
        thread = transport._reconnect_thread
        thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(attempts), 3)
        self.assertTrue(all(attempts))
        self.assertEqual(handler.attempt_number, 3)
        self.assertFalse(handler.reconnecting)
        self.assertTrue(transport.is_disconnected())

    def test_handle_reconnect_ignores_manual_close(self):
        transport = self.build_transport(
            RawReconnectionHandler(sleep_time=0.001, max_attempts=2))
        transport._client = Mock()
        transport.manually_closing = True

        self.assertFalse(transport.handle_reconnect())

    def test_handle_reconnect_ignores_open_connection(self):
        transport = self.build_transport(
            RawReconnectionHandler(sleep_time=0.001, max_attempts=2))
        client = Mock()
        client.is_connection_closed.return_value = False
        transport._client = client

        self.assertFalse(transport.handle_reconnect())

    def test_handle_reconnect_does_not_spawn_duplicate_loop(self):
        transport = self.build_transport(
            RawReconnectionHandler(sleep_time=0.001, max_attempts=2))
        client = Mock()
        client.is_connection_closed.return_value = True
        transport._client = client

        release = threading.Event()
        worker = threading.Thread(target=release.wait)
        worker.start()
        transport._reconnect_thread = worker

        try:
            self.assertTrue(transport.handle_reconnect())
            self.assertTrue(transport._reconnect_pending)
            self.assertIs(transport._reconnect_thread, worker)
        finally:
            release.set()
            worker.join(timeout=2)

    def test_send_does_not_reset_reconnection_attempts(self):
        handler = Mock()
        handler.reconnecting = False
        transport = self.build_transport(handler)
        transport._client = Mock()

        transport.send(PingMessage())

        handler.reset.assert_not_called()

    def test_successful_handshake_resets_reconnection_attempts(self):
        handler = RawReconnectionHandler(sleep_time=0.001, max_attempts=5)
        handler.next()
        handler.next()
        transport = self.build_transport(handler)

        try:
            transport.evaluate_handshake("{}\x1e")

            self.assertEqual(handler.attempt_number, 0)
            self.assertFalse(handler.reconnecting)
            self.assertTrue(transport.is_connected())
        finally:
            transport.connection_checker.stop()

    def test_sse_successful_handshake_resets_reconnection_attempts(self):
        handler = RawReconnectionHandler(sleep_time=0.001, max_attempts=5)
        handler.next()
        transport = SSETransport(
            protocol=JsonHubProtocol(),
            reconnection_handler=handler,
            on_open=lambda: None,
            on_close=lambda: None)

        # Pretend the checker is running so evaluate_handshake does not
        # spawn a real thread (no client is set in this test).
        transport.connection_checker.running = True
        try:
            transport.evaluate_handshake("{}\x1e")

            self.assertEqual(handler.attempt_number, 0)
            self.assertFalse(handler.reconnecting)
        finally:
            transport.connection_checker.stop()

    def test_long_polling_successful_handshake_resets_attempts(self):
        handler = RawReconnectionHandler(sleep_time=0.001, max_attempts=5)
        handler.next()
        transport = LongPollingTransport(
            protocol=JsonHubProtocol(),
            reconnection_handler=handler,
            on_open=lambda: None,
            on_close=lambda: None)

        # Pretend the checker is running so evaluate_handshake does not
        # spawn a real thread (no client is set in this test).
        transport.connection_checker.running = True
        try:
            transport.evaluate_handshake("{}\x1e")

            self.assertEqual(handler.attempt_number, 0)
            self.assertFalse(handler.reconnecting)
        finally:
            transport.connection_checker.stop()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
