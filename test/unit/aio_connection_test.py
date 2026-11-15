import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from signalrcore.aio.hub.aio_auth_hub_connection import (
    AIOAuthHubConnection,
)
from signalrcore.aio.hub.aio_base_hub_connection import (
    AIOBaseHubConnection,
)
from signalrcore.hub.errors import HubConnectionError
from signalrcore.hub.negotiation import AvailableTransport, NegotiateResponse
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.transport.base_transport import TransportState
from signalrcore.types import HttpTransportType, HubProtocolEncoding

MIXIN = "signalrcore.aio.hub.aio_connection_mixin"


def negotiated(headers=None):
    return (
        "ws://example.com/chat",
        headers or {},
        negotiate_response())


def negotiate_response():
    return NegotiateResponse(
        negotiate_version=1,
        connection_id="connection-id",
        connection_token="connection-token",
        access_token=None,
        url="ws://example.com/chat",
        available_transports=[
            AvailableTransport(
                transport=HttpTransportType.web_sockets,
                transfer_formats=[HubProtocolEncoding.text])
        ])


class FakeTransport(object):
    def __init__(self, connects=True, wait_error=None):
        self.state = TransportState.disconnected
        self.connects = connects
        self.wait_error = wait_error
        self.started = False
        self.stopped = False
        self.sent = []
        self.disposed = False

    async def start(self):
        self.started = True
        if self.connects:
            self.state = TransportState.connected

    async def stop(self):
        self.stopped = True
        self.state = TransportState.disconnected

    def is_connected(self):
        return self.state == TransportState.connected

    def is_disconnected(self):
        return self.state == TransportState.disconnected

    def is_running(self):
        return self.state != TransportState.disconnected

    async def wait_until(self, predicate, timeout=None):
        if self.wait_error is not None:
            raise self.wait_error
        if not predicate():
            raise TimeoutError("state not reached")

    async def send(self, message, on_invocation=None):
        self.sent.append(message)

    async def dispose(self):
        self.disposed = True


def build_base(**kwargs):
    kwargs.setdefault("url", "http://localhost/hub")
    kwargs.setdefault("protocol", JsonHubProtocol())
    return AIOBaseHubConnection(**kwargs)


def build_auth(auth_function=None, **kwargs):
    kwargs.setdefault("url", "http://localhost/hub")
    kwargs.setdefault("protocol", JsonHubProtocol())
    return AIOAuthHubConnection(
        auth_function=auth_function or (lambda: "token"),
        **kwargs)


class AIOStopTest(unittest.IsolatedAsyncioTestCase):
    async def test_stop_before_start_returns(self):
        for factory in (build_base, build_auth):
            with self.subTest(connection=factory.__name__):
                connection = factory()

                await asyncio.wait_for(connection.stop(), timeout=1)

                self.assertIsNone(connection.transport)

    async def test_stop_awaits_transport_stop(self):
        for factory in (build_base, build_auth):
            with self.subTest(connection=factory.__name__):
                connection = factory()
                transport = FakeTransport()
                connection.transport = transport

                await connection.stop()

                self.assertTrue(transport.stopped)
                self.assertTrue(transport.is_disconnected())


class AIOStartTest(unittest.IsolatedAsyncioTestCase):
    async def _start_connection(self, connection, transport=None):
        transport = transport or FakeTransport()

        with patch(
                MIXIN + ".AsyncNegotiationHandler") as handler, patch(
                MIXIN + ".AIOTransportFactory.create",
                return_value=transport) as create:
            handler.return_value.negotiate = AsyncMock(
                return_value=negotiated())

            result = await connection.start()

        return result, transport, create

    async def test_start_creates_and_starts_transport(self):
        connection = build_base()

        result, transport, create = await self._start_connection(connection)

        self.assertTrue(result)
        self.assertTrue(transport.started)
        self.assertIs(connection.transport, transport)
        self.assertEqual(connection.url, "ws://example.com/chat")
        create.assert_called_once()

    async def test_start_returns_false_when_already_connected(self):
        connection = build_base()
        connection.transport = FakeTransport()
        connection.transport.state = TransportState.connected

        self.assertFalse(await connection.start())

    async def test_start_raises_when_connection_closes(self):
        connection = build_base()

        with self.assertRaises(HubConnectionError):
            await self._start_connection(
                connection, FakeTransport(connects=False))

    async def test_start_timeout_stops_transport(self):
        connection = build_base()
        transport = FakeTransport(wait_error=asyncio.TimeoutError())

        with self.assertRaises(TimeoutError):
            await self._start_connection(connection, transport)

        self.assertTrue(transport.stopped)

    async def test_negotiation_error_is_propagated(self):
        connection = build_base()

        with patch(
                MIXIN + ".AsyncNegotiationHandler") as handler:
            handler.return_value.negotiate = AsyncMock(
                side_effect=RuntimeError("boom"))

            with self.assertRaises(RuntimeError):
                await asyncio.wait_for(connection.start(), timeout=1)


class AIOAuthStartTest(unittest.IsolatedAsyncioTestCase):
    async def test_sync_auth_function_sets_token_header(self):
        connection = build_auth(auth_function=lambda: "sync-token")

        with patch(
                MIXIN + ".AsyncNegotiationHandler") as handler, patch(
                MIXIN + ".AIOTransportFactory.create",
                return_value=FakeTransport()):
            handler.return_value.negotiate = AsyncMock(
                return_value=negotiated(
                    {"Authorization": "Bearer sync-token"}))

            await connection.start()

        self.assertEqual(connection.token, "sync-token")
        self.assertEqual(
            connection.headers["Authorization"], "Bearer sync-token")

    async def test_async_auth_function_sets_token_header(self):
        async def auth():
            await asyncio.sleep(0)
            return "async-token"

        connection = build_auth(auth_function=auth)

        with patch(
                MIXIN + ".AsyncNegotiationHandler") as handler, patch(
                MIXIN + ".AIOTransportFactory.create",
                return_value=FakeTransport()):
            handler.return_value.negotiate = AsyncMock(
                return_value=negotiated(
                    {"Authorization": "Bearer async-token"}))

            await connection.start()

        self.assertEqual(
            connection.headers["Authorization"], "Bearer async-token")

    async def test_auth_error_is_propagated(self):
        def auth():
            raise RuntimeError("no token")

        connection = build_auth(auth_function=auth)

        with self.assertRaises(RuntimeError):
            await connection.start()


class AIOWaitUntilStateTest(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_raises(self):
        connection = build_base()

        with self.assertRaises(TimeoutError):
            await connection.wait_until_state(
                TransportState.connected, timeout=0.05)

    async def test_missing_transport_is_disconnected(self):
        connection = build_base()

        await asyncio.wait_for(
            connection.wait_until_state(TransportState.disconnected),
            timeout=1)


class AIOInvokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_invoke_requires_running_transport(self):
        connection = build_base()

        with self.assertRaises(HubConnectionError):
            await connection.invoke("Send", ["hello"])

        connection.transport = FakeTransport()

        with self.assertRaises(HubConnectionError):
            await connection.invoke("Send", ["hello"])

    async def test_invoke_awaits_transport_send(self):
        connection = build_base()
        transport = FakeTransport()
        transport.state = TransportState.connected
        connection.transport = transport

        result = await connection.invoke(
            "Send", ["hello"], invocation_id="invocation-id")

        self.assertEqual(result.invocation_id, "invocation-id")
        self.assertEqual(len(transport.sent), 1)
        self.assertEqual(transport.sent[0].target, "Send")

    async def test_invoke_rejects_invalid_arguments(self):
        connection = build_base()
        transport = FakeTransport()
        transport.state = TransportState.connected
        connection.transport = transport

        with self.assertRaises(TypeError):
            await connection.invoke("Send", "hello")

    async def test_invoke_callback_is_registered(self):
        connection = build_base()
        transport = FakeTransport()
        transport.state = TransportState.connected
        connection.transport = transport

        callback = AsyncMock()

        await connection.invoke(
            "Send", ["hello"], on_invocation=callback)

        handlers = connection.stream_handlers[
            transport.sent[0].invocation_id]

        self.assertEqual(len(handlers), 1)
        self.assertIs(handlers[0].complete_callback, callback)

    async def test_stream_registers_handler_and_sends_message(self):
        connection = build_base()
        transport = FakeTransport()
        transport.state = TransportState.connected
        connection.transport = transport

        handler = await connection.stream("Counter", [10, 500])

        self.assertEqual(handler.event, "Counter")
        self.assertIn(handler.invocation_id, connection.stream_handlers)
        self.assertEqual(
            transport.sent[0].invocation_id, handler.invocation_id)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
