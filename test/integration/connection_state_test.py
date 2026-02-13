import time
import threading
from ..base_test_case import BaseTestCase, LOCK_TIMEOUT, CONNECTION_TIMEOUT

LOCKS = {}


class ConnectionWebSocketStateTest(BaseTestCase):
    def test_delay_sending(self):
        identifier = self.get_random_id()
        result = None

        LOCKS[identifier] = threading.Lock()

        time.sleep(CONNECTION_TIMEOUT)

        def release(completion_message):
            global LOCKS

            while result is None:
                time.sleep(1)

            self.logger.debug(f"{completion_message}")

            if result.invocation_id == completion_message.invocation_id:
                LOCKS[identifier].release()

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))

        result = self.connection.invoke(
            "SendMessage", ["user", "msg"], release)

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT * 2))

        time.sleep(CONNECTION_TIMEOUT)

        result = None
        result = self.connection.send("SendMessage", ["user", "msg"], release)

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT * 3))


class ConnectionWebSocketMessagePackStateTest(ConnectionWebSocketStateTest):
    def get_connection(self):
        return super().get_connection(msgpack=True)


class ConnectionSseStateTest(ConnectionWebSocketStateTest):
    def get_connection(self, msgpack=False):
        return super().get_connection_sse(reconnection=True)


class ConnectionLongPollingStateTest(ConnectionWebSocketStateTest):
    def get_connection(self, msgpack=False):
        return super().get_connection_long_polling(reconnection=True)

    def test_delay_sending(self):
        identifier = self.get_random_id()
        LOCKS[identifier] = threading.Lock()

        time.sleep(CONNECTION_TIMEOUT)

        def release(args, orig_msg):
            global LOCKS
            username, msg = args

            self.logger.debug(f"{username} {msg}")

            if orig_msg == msg:
                LOCKS[identifier].release()

        self.connection.on(
            "ReceiveMessage",
            lambda args: release(args, "msg 1"))

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))
        self.connection.send("SendMessage", ["user", "msg 1"])
        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT * 4))

        time.sleep(CONNECTION_TIMEOUT/4)

        self.connection.on(
            "ReceiveMessage",
            lambda args: release(args, "msg 2"))

        self.connection.send("SendMessage", ["user", "msg 2"])

        time.sleep(CONNECTION_TIMEOUT)

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT * 4))
