import threading
from typing import Dict
from ...aio_base_test_case import AIOConnectionBaseTestCase


LOCKS: Dict[str, threading.Lock] = {}


class AIOSendTests(AIOConnectionBaseTestCase):
    async def test_aio_send(self):

        identifier = self.get_random_id()
        LOCKS[identifier] = threading.Lock()

        def release(msg):
            if identifier in msg[1]:
                LOCKS[identifier].release()

        self.connection.on("ReceiveMessage", release)
        message = "new message {0}".format(identifier)
        username = "mandrewcito"

        self.assertTrue(
            LOCKS[identifier].acquire(timeout=10))

        await self.connection.send("SendMessage", [username, message])

        self.assertTrue(
            LOCKS[identifier].acquire(timeout=10))
