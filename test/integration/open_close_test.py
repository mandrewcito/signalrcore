import logging
import threading
import uuid
import time

from signalrcore.types import HttpTransportType
from signalrcore.hub_connection_builder import HubConnectionBuilder
from ..base_test_case import BaseTestCase

LOCKS = {}


class TestStartMethod(BaseTestCase):
    def setUp(self):  # pragma: no cover
        pass

    def tearDown(self):  # pragma: no cover
        pass

    def test_start(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .build()

        identifier = str(uuid.uuid4())
        LOCKS[identifier] = threading.Lock()

        def release():
            LOCKS[identifier].release()

        self.assertTrue(LOCKS[identifier].acquire(timeout=30))

        connection.on_open(release)
        connection.on_close(release)

        result = connection.start()

        self.assertTrue(result)

        self.assertTrue(LOCKS[identifier].acquire(timeout=30))
        # Released on open

        result = connection.start()

        self.assertFalse(result)

        connection.stop()

        del LOCKS[identifier]
        del connection


class TestOpenCloseWebsocketMethods(BaseTestCase):
    def setUp(self):  # pragma: no cover
        pass

    def tearDown(self):  # pragma: no cover
        pass

    def _test(self, connection, sleep_time: int = 1):

        identifier = str(uuid.uuid4())
        LOCKS[identifier] = threading.Lock()

        def release(msg):
            self.logger.debug(msg)
            LOCKS[identifier].release()

        connection.on_open(lambda: release("open"))
        connection.on_close(lambda: release("close"))

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))

        connection.start()

        self.assertTrue(
            LOCKS[identifier].acquire(timeout=10),
            "on_open was not fired")

        connection.on_open(lambda: None)

        time.sleep(sleep_time)

        connection.stop()

        self.assertTrue(
            LOCKS[identifier].acquire(timeout=10),
            "on_close was not fired")

        del LOCKS[identifier]

    def test_open_close(self):
        connection = self.get_connection()
        self._test(connection)


class TestOpenCloseSseMethods(TestOpenCloseWebsocketMethods):
    def setUp(self):  # pragma: no cover
        pass

    def tearDown(self):  # pragma: no cover
        pass

    def get_connection(self, msgpack=False):
        return HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.server_sent_events
            })\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })\
            .build()

    def test_open_close(self):
        connection = self.get_connection()
        self._test(connection)
        del connection

    def test_open_wait_close(self):
        connection = self.get_connection()
        self._test(connection, 10)
        del connection


class TestOpenCloseLongPollingMethods(TestOpenCloseSseMethods):
    def get_connection(self, msgpack=False):
        return super().get_connection_long_polling(
            False,
            msgpack)
