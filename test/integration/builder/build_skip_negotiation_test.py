import threading
from typing import Dict
from ...base_test_case import BaseTestCase

LOCKS: Dict[str, threading.Lock] = {}


class SkipNegotiationBuildTest(BaseTestCase):
    def get_connection(self, msgpack=False):
        options = {"verify_ssl": False, "skip_negotiation": True}
        return super().get_connection(msgpack, options=options)

    def test_skip_negotiation(self):

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

        self.connection.send("SendMessage", [username, message])

        self.assertTrue(
            LOCKS[identifier].acquire(timeout=10))

        del LOCKS[identifier]
