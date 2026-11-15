import asyncio
import unittest
from unittest.mock import Mock, patch

from signalrcore.aio.hub.aio_auth_hub_connection import \
    AIOAuthHubConnection
from signalrcore.aio.hub.aio_base_hub_connection import \
    AIOBaseHubConnection
from signalrcore.hub.base_hub_connection import BaseHubConnection
from signalrcore.transport.base_transport import TransportState


def build_base():
    return AIOBaseHubConnection(url="http://localhost/hub")


def build_auth():
    return AIOAuthHubConnection(
        auth_function=lambda: "token",
        url="http://localhost/hub")


CONNECTIONS = (build_base, build_auth)


class AIOStopTest(unittest.IsolatedAsyncioTestCase):
    async def test_stop_before_start_returns(self):
        for factory in CONNECTIONS:
            with self.subTest(connection=factory.__name__):
                connection = factory()

                await asyncio.wait_for(connection.stop(), timeout=1)

                self.assertIsNone(connection.transport)

    async def test_stop_waits_for_disconnected_transport(self):
        connection = build_base()
        connection.transport = Mock()
        connection.transport.state = TransportState.disconnected

        with patch.object(BaseHubConnection, "stop", return_value=None):
            await asyncio.wait_for(connection.stop(), timeout=1)


class AIOStartFailureTest(unittest.IsolatedAsyncioTestCase):
    async def test_start_error_is_propagated_without_hanging(self):
        for factory in CONNECTIONS:
            with self.subTest(connection=factory.__name__):
                connection = factory()

                with patch.object(
                        BaseHubConnection,
                        "start",
                        side_effect=RuntimeError("boom")):
                    with self.assertRaises(RuntimeError):
                        await asyncio.wait_for(
                            connection.start(), timeout=1)


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

    async def test_start_returns_when_connected(self):
        connection = build_base()
        connection.transport = Mock()
        connection.transport.state = TransportState.connected

        with patch.object(BaseHubConnection, "start", return_value=True):
            result = await asyncio.wait_for(
                connection.start(), timeout=1)

        self.assertTrue(result)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
