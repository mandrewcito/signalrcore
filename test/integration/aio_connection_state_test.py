import asyncio

from signalrcore.aio.hub.aio_base_hub_connection import (
    AIOBaseHubConnection,
)
from signalrcore.hub.errors import HubConnectionError
from signalrcore.transport.base_transport import TransportState

from ..aio_base_test_case import AIOBaseTestCase, AIOConnectionBaseTestCase


class AIOConnectionLifecycleTest(AIOBaseTestCase):
    async def test_start_twice(self):
        connection = await self.start_connection()

        try:
            self.assertFalse(await connection.start())
            await connection.wait_until_state(
                TransportState.connected, timeout=5)
        finally:
            await connection.stop()

        await connection.wait_until_state(
            TransportState.disconnected, timeout=5)
        self.assertTrue(connection.transport.is_disconnected())

    async def test_stop_before_start(self):
        connection = AIOBaseHubConnection(url="http://localhost/hub")

        await asyncio.wait_for(connection.stop(), timeout=1)
        await asyncio.wait_for(
            connection.wait_until_state(
                TransportState.disconnected, timeout=1),
            timeout=1)

    async def test_send_after_stop_raises(self):
        connection = await self.start_connection()

        await connection.stop()

        with self.assertRaises(HubConnectionError):
            await connection.send("SendMessage", ["user", "message"])

        with self.assertRaises(HubConnectionError):
            await connection.invoke("SendMessage", ["user", "message"])

        with self.assertRaises(HubConnectionError):
            await connection.stream("Counter", [10, 100])


class AIOConnectionStateTest(AIOConnectionBaseTestCase):
    async def test_wait_until_connected(self):
        await self.connection.wait_until_state(
            TransportState.connected, timeout=5)
        self.assertTrue(self.connection.transport.is_connected())

    async def test_wait_until_disconnected(self):
        await self.connection.stop()

        await asyncio.wait_for(
            self.connection.wait_until_state(
                TransportState.disconnected, timeout=5),
            timeout=5)

    async def test_subscribe_and_unsubscribe(self):
        def fake_callback(_):
            pass

        self.connection.on("ReceiveMessage", fake_callback)
        self.assertEqual(len(self.connection.handlers), 1)

        self.connection.unsubscribe("ReceiveMessage", fake_callback)
        self.assertEqual(len(self.connection.handlers), 0)
