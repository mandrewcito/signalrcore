import asyncio
import time
import unittest
from unittest.mock import patch

from signalrcore.aio.transport.base_transport import AIOBaseTransport
from signalrcore.aio.transport.factory import AIOTransportFactory
from signalrcore.aio.transport.long_polling.transport import (
    AIOLongPollingTransport,
)
from signalrcore.aio.transport.sse.transport import AIOSSETransport
from signalrcore.aio.transport.websockets.transport import (
    AIOWebsocketTransport,
)
from signalrcore.hub.negotiation import AvailableTransport, NegotiateResponse
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.transport.base_transport import TransportState
from signalrcore.transport.reconnection import RawReconnectionHandler
from signalrcore.types import HttpTransportType, HubProtocolEncoding

FACTORY = "signalrcore.aio.transport.factory"


class FakeClient(object):
    def __init__(self, connect_error=None):
        self.connect_calls = 0
        self.close_calls = 0
        self.dispose_calls = 0
        self.connect_error = connect_error
        self.closed = True

    async def connect(self):
        self.connect_calls += 1
        if self.connect_error is not None:
            raise self.connect_error
        self.closed = False

    def is_connection_closed(self):
        return self.closed

    async def close(self):
        self.close_calls += 1
        self.closed = True

    async def dispose(self):
        self.dispose_calls += 1
        self.closed = True

    def is_trace_enabled(self):
        return False


class FakeTransport(AIOBaseTransport):
    def __init__(self, client=None, **kwargs):
        self.client = client if client is not None else FakeClient()
        self.sent = []
        self.pings = 0
        self.negotiations = 0
        self.ping_function = self.ping
        kwargs.setdefault("url", "ws://example.com/chat")
        super().__init__(**kwargs)
        self._client = self.client

    def create_client(self):
        return self.client

    async def negotiate(self):
        self.negotiations += 1
        return None

    async def send(self, message, on_invocation=None):
        self.sent.append(message)

    async def ping(self):
        self.pings += 1


def negotiate_response(*transports):
    return NegotiateResponse(
        negotiate_version=1,
        connection_id="connection-id",
        connection_token=None,
        access_token=None,
        url="ws://example.com/chat",
        available_transports=[
            AvailableTransport(
                transport=transport,
                transfer_formats=[HubProtocolEncoding.text])
            for transport in transports
        ])


class AIOTransportFactoryTest(unittest.TestCase):
    def setUp(self):
        self.kwargs = {"url": "ws://example.com/chat"}

    @patch(FACTORY + ".AIOLongPollingTransport")
    @patch(FACTORY + ".AIOSSETransport")
    @patch(FACTORY + ".AIOWebsocketTransport")
    def test_websockets_are_preferred(
            self, websockets, sse, long_polling):
        result = AIOTransportFactory.create(
            negotiate_response(
                HttpTransportType.long_polling,
                HttpTransportType.server_sent_events,
                HttpTransportType.web_sockets),
            None,
            **self.kwargs)

        self.assertIs(result, websockets.return_value)
        websockets.assert_called_once_with(**self.kwargs)

    def test_preferred_transport_wins(self):
        result = AIOTransportFactory.create(
            negotiate_response(
                HttpTransportType.web_sockets,
                HttpTransportType.long_polling),
            HttpTransportType.long_polling,
            url="ws://example.com/chat",
            protocol=JsonHubProtocol())

        self.assertIsInstance(result, AIOLongPollingTransport)

    def test_every_transport_is_selectable(self):
        cases = (
            (HttpTransportType.web_sockets, AIOWebsocketTransport),
            (HttpTransportType.server_sent_events, AIOSSETransport),
            (HttpTransportType.long_polling, AIOLongPollingTransport),
        )

        for transport_type, expected in cases:
            with self.subTest(transport=transport_type):
                result = AIOTransportFactory.create(
                    negotiate_response(transport_type),
                    transport_type,
                    url="ws://example.com/chat",
                    protocol=JsonHubProtocol())
                self.assertIsInstance(result, expected)


class AIOBaseTransportStateTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_connects_and_waits_for_connected(self):
        transport = FakeTransport()

        await transport.start()

        self.assertEqual(transport.client.connect_calls, 1)
        self.assertTrue(transport.is_connecting())

        waiter = asyncio.ensure_future(
            transport.wait_until_state(TransportState.connected, timeout=1))
        await asyncio.sleep(0)
        await transport._set_state(TransportState.connected)

        await waiter
        self.assertTrue(transport.is_connected())

    async def test_state_callbacks_are_awaited(self):
        events = []

        async def on_open():
            await asyncio.sleep(0)
            events.append("open")

        async def on_close():
            await asyncio.sleep(0)
            events.append("close")

        async def on_reconnect():
            await asyncio.sleep(0)
            events.append("reconnect")

        transport = FakeTransport(
            on_open=on_open,
            on_close=on_close,
            on_reconnect=on_reconnect)

        await transport._set_state(TransportState.connecting)
        await transport._set_state(TransportState.connected)
        await transport._set_state(TransportState.reconnecting)
        await transport._set_state(TransportState.connected)
        await transport._set_state(TransportState.disconnected)

        self.assertEqual(
            events, ["open", "reconnect", "close"])

    async def test_sync_callbacks_are_supported(self):
        events = []

        transport = FakeTransport(on_open=lambda: events.append("open"))

        await transport._set_state(TransportState.connecting)
        await transport._set_state(TransportState.connected)

        self.assertEqual(events, ["open"])

    async def test_wait_until_state_times_out(self):
        transport = FakeTransport()

        with self.assertRaises(asyncio.TimeoutError):
            await transport.wait_until_state(
                TransportState.connected, timeout=0.01)


class AIOBaseTransportKeepAliveTest(unittest.IsolatedAsyncioTestCase):
    async def test_keepalive_pings_after_interval(self):
        transport = FakeTransport()
        transport.keep_alive_interval = 0.01
        transport.last_message = time.time() - 1

        await transport._set_state(TransportState.connecting)
        transport._start_keepalive()

        try:
            while transport.pings == 0:
                await asyncio.sleep(0.01)
        finally:
            await transport.stop()

        self.assertGreaterEqual(transport.pings, 1)
        self.assertTrue(transport.is_disconnected())

    async def test_stop_cancels_keepalive(self):
        transport = FakeTransport()
        transport.keep_alive_interval = 0.01
        transport.last_message = time.time() - 1

        await transport._set_state(TransportState.connecting)
        transport._start_keepalive()
        await asyncio.sleep(0.02)

        task = transport._keepalive_task
        await transport.stop()

        self.assertTrue(task.done())
        self.assertIsNone(transport._keepalive_task)


class AIOBaseTransportReconnectTest(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_restarts_the_client(self):
        reconnects = []

        async def on_reconnect():
            reconnects.append(True)

        transport = FakeTransport(
            reconnection_handler=RawReconnectionHandler(0.01, None),
            on_reconnect=on_reconnect)

        await transport._set_state(TransportState.connected)
        transport.client.closed = True

        self.assertTrue(await transport.handle_reconnect())

        while transport.client.connect_calls < 1:
            await asyncio.sleep(0.01)

        self.assertEqual(transport.negotiations, 1)
        self.assertTrue(transport.is_reconnecting())

        await transport._set_state(TransportState.connected)
        await asyncio.sleep(0)

        self.assertEqual(reconnects, [True])
        await transport.stop()

    async def test_duplicate_reconnect_does_not_start_a_second_loop(self):
        transport = FakeTransport(
            reconnection_handler=RawReconnectionHandler(10, None))

        await transport._set_state(TransportState.connected)
        transport.client.closed = True

        self.assertTrue(await transport.handle_reconnect())
        task = transport._reconnect_task

        self.assertTrue(await transport.handle_reconnect())

        self.assertIs(transport._reconnect_task, task)

        await transport.stop()

    async def test_reconnect_is_skipped_when_client_is_open(self):
        transport = FakeTransport(
            reconnection_handler=RawReconnectionHandler(0.01, None))

        await transport._set_state(TransportState.connected)
        transport.client.closed = False

        self.assertFalse(await transport.handle_reconnect())
        self.assertIsNone(transport._reconnect_task)

    async def test_reconnect_without_handler_is_skipped(self):
        transport = FakeTransport()

        await transport._set_state(TransportState.connected)
        transport.client.closed = True

        self.assertFalse(await transport.handle_reconnect())

    async def test_max_attempts_ends_disconnected(self):
        client = FakeClient(connect_error=OSError("boom"))
        transport = FakeTransport(
            client=client,
            reconnection_handler=RawReconnectionHandler(0.01, 1))

        await transport._set_state(TransportState.connected)
        client.closed = True

        self.assertTrue(await transport.handle_reconnect())

        await asyncio.wait_for(
            transport.wait_until_state(
                TransportState.disconnected, timeout=2),
            timeout=2)

        self.assertGreaterEqual(client.connect_calls, 1)
        self.assertFalse(transport.reconnection_handler.reconnecting)

    async def test_stop_during_reconnect_finishes_promptly(self):
        transport = FakeTransport(
            reconnection_handler=RawReconnectionHandler(60, None))

        await transport._set_state(TransportState.connected)
        transport.client.closed = True
        await transport.handle_reconnect()

        task = transport._reconnect_task
        self.assertFalse(task.done())

        await asyncio.wait_for(transport.stop(), timeout=1)

        self.assertTrue(task.done())
        self.assertTrue(transport.is_disconnected())


class AIOWebsocketTransportHandshakeTest(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_sets_connected_and_reports_messages(self):
        messages = []

        transport = AIOWebsocketTransport(
            url="ws://example.com/chat",
            protocol=JsonHubProtocol(),
            on_message=lambda received: messages.extend(received))

        client = FakeClient()
        transport._client = client
        transport.create_client = lambda: client

        await transport._set_state(TransportState.connecting)

        await transport.on_message(
            transport, '{}\x1e{"type":6}\x1e')

        self.assertTrue(transport.handshake_received)
        self.assertTrue(transport.is_connected())
        self.assertEqual(len(messages), 1)

        await transport.stop()

    async def test_rejected_handshake_stops_connection(self):
        transport = AIOWebsocketTransport(
            url="ws://example.com/chat",
            protocol=JsonHubProtocol())

        client = FakeClient()
        transport._client = client
        transport.create_client = lambda: client
        await transport._set_state(TransportState.connecting)

        await transport.on_message(
            transport, '{"error":"nope"}\x1e')

        self.assertFalse(transport.handshake_received)
        self.assertTrue(transport.is_disconnected())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
