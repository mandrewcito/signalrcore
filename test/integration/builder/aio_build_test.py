import threading
from typing import Dict
from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder
from signalrcore.transport.base_transport import TransportState
from ...aio_base_test_case import AIOBaseTestCase

LOCKS: Dict[str, threading.Lock] = {}


class AIOBuildTest(AIOBaseTestCase):

    async def test_build(self):
        options = {"verify_ssl": False}

        builder = AIOHubConnectionBuilder()\
            .with_url(self.server_url, options=options)\
            .configure_logging(
                self.get_log_level(),
                socket_trace=self.is_debug())\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })

        hub = builder.build()

        await hub.start()

        identifier = self.get_random_id()
        LOCKS[identifier] = threading.Lock()

        def release(msg):
            if identifier in msg[1]:
                LOCKS[identifier].release()

        hub.on("ReceiveMessage", release)
        message = "new message {0}".format(identifier)
        username = "mandrewcito"

        self.assertTrue(
            LOCKS[identifier].acquire(timeout=10))

        await hub.send("SendMessage", [username, message])

        self.assertTrue(
            LOCKS[identifier].acquire(timeout=10))

        self.assertEqual(
            TransportState.connected,
            hub.transport.state)

        await hub.stop()
