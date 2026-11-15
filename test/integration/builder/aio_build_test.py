import asyncio

from signalrcore.transport.base_transport import TransportState

from ...aio_base_test_case import AIOBaseTestCase


class AIOBuildTest(AIOBaseTestCase):
    async def test_build(self):
        hub = self.build_connection()

        await hub.start()

        try:
            identifier = self.get_random_id()
            received = asyncio.Event()

            def release(msg):
                if identifier in msg[1]:
                    received.set()

            hub.on("ReceiveMessage", release)
            message = "new message {0}".format(identifier)

            await hub.send("SendMessage", ["mandrewcito", message])
            await asyncio.wait_for(received.wait(), timeout=10)

            self.assertEqual(
                TransportState.connected,
                hub.transport.state)
        finally:
            await hub.stop()

        self.assertTrue(hub.transport.is_disconnected())
