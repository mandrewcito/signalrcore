import asyncio

from signalrcore.types import HttpTransportType
from signalrcore.transport.base_transport import TransportState

from ...aio_base_test_case import AIOBaseTestCase, Urls


class TestAIOReconnect(AIOBaseTestCase):
    """Automatic reconnection after the server closes the connection."""

    async def test_reconnect(self):
        connection = self.build_connection(reconnection=True)
        opened = asyncio.Event()
        reconnected = asyncio.Event()

        connection.on_open(opened.set)
        connection.on_reconnect(reconnected.set)

        try:
            await connection.start()
            await asyncio.wait_for(opened.wait(), timeout=10)

            # Server closes the connection on purpose.
            await connection.send("DisconnectMe", [])

            await asyncio.wait_for(reconnected.wait(), timeout=30)
            await connection.wait_until_state(
                TransportState.connected, timeout=10)

            self.assertTrue(connection.transport.is_connected())
        finally:
            await connection.stop()

        await connection.wait_until_state(
            TransportState.disconnected, timeout=5)


class TestAIOSseReconnect(TestAIOReconnect):
    def build_connection(self, **kwargs):
        kwargs.setdefault("url", Urls.ws_to_http(self.server_url))
        kwargs.setdefault(
            "transport", HttpTransportType.server_sent_events)
        return super().build_connection(**kwargs)


class TestAIOLongPollingReconnect(TestAIOReconnect):
    def build_connection(self, **kwargs):
        kwargs.setdefault("url", Urls.ws_to_http(self.server_url))
        kwargs.setdefault(
            "transport", HttpTransportType.long_polling)
        return super().build_connection(**kwargs)
