import time
import threading
from .base_test_case import BaseTestCase, LOCK_TIMEOUT

LOCKS = {}


class ConnectionWebSocketStateTest(BaseTestCase):
    def test_delay_sending(self):
        identifier = self.get_random_id()
        LOCKS[identifier] = threading.Lock()
        time.sleep(20)

        def release(msg=None):
            global LOCKS
            LOCKS[identifier].release()

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))
        self.connection.send("SendMessage", ["user", "msg"], release)
        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))

        time.sleep(20)

        self.connection.send("SendMessage", ["user", "msg"], release)
        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))


class ConnectionSseStateTest(ConnectionWebSocketStateTest):
    def get_connection(self, msgpack=False):
        return super().get_connection_sse(reconnection=True)


class ConnectionLongPollingStateTest(ConnectionWebSocketStateTest):
    def get_connection(self, msgpack=False):
        return super().get_connection_long_polling(reconnection=True)

    def test_delay_sending(self):
        identifier = self.get_random_id()
        LOCKS[identifier] = threading.Lock()
        time.sleep(20)

        def release(msg=None):
            global LOCKS
            LOCKS[identifier].release()

        self.connection.on("ReceiveMessage", release)

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))
        self.connection.send("SendMessage", ["user", "msg 1"])
        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT * 2))

        time.sleep(20)

        self.connection.send("SendMessage", ["user", "msg 2"])
        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT * 3))
