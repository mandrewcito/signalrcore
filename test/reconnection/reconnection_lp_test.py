import logging
import uuid
import threading
from typing import Dict
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.hub.errors import HubConnectionError
from test.base_test_case import BaseTestCase
from signalrcore.types import HttpTransportType

LOCKS: Dict[str, threading.Lock] = {}


class TestLongPollingReconnect(BaseTestCase):

    def setUp(self):  # pragma: no cover
        pass

    def tearDown(self):  # pragma: no cover
        pass

    def test_reconnect_interval_config(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.long_polling})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "interval",
                "intervals": [1, 2, 4, 45, 6, 7, 8, 9, 10],
                "keep_alive_interval": 5
            })\
            .build()

        identifier = str(uuid.uuid4())
        LOCKS[identifier] = threading.Lock()

        def release():
            LOCKS[identifier].release()

        connection.on_open(release)
        connection.on_close(release)

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))

        connection.start()

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))

        connection.stop()

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))

        del LOCKS[identifier]

    def test_reconnect_interval(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.long_polling})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "interval",
                "intervals": [1, 2, 4, 45, 6, 7, 8, 9, 10],
                "keep_alive_interval": 3
            })\
            .build()
        self.reconnect_test(connection)

    def test_no_reconnect(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.long_polling})\
            .configure_logging(logging.ERROR)\
            .build()

        identifier = str(uuid.uuid4())
        LOCKS[identifier] = threading.Lock()

        def release(msg=None):
            LOCKS[identifier].release()

        LOCKS[identifier].acquire(timeout=10)

        connection.on_open(release)

        connection.start()

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))
        # Released on open

        connection.send("DisconnectMe", [])

        connection.on_open(lambda: None)
        connection.on_close(release)

        # Released on close
        self.assertTrue(LOCKS[identifier].acquire(timeout=20))

        self.assertRaises(
            HubConnectionError,
            lambda: connection.send("DisconnectMe", []))

        connection.stop()
        del LOCKS[identifier]

    def reconnect_test(self, connection):
        identifier = str(uuid.uuid4())
        LOCKS[identifier] = threading.Lock()

        def release():
            LOCKS[identifier].release()

        connection.on_open(release)
        connection.on_reconnect(release)

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))

        connection.start()

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))

        connection.on_open(lambda: None)

        # Release on Open
        connection.send("DisconnectMe", [])

        self.assertTrue(LOCKS[identifier].acquire(timeout=20))
        # released on reopen

        connection.stop()
        del LOCKS[identifier]

    def test_raw_reconnection(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.long_polling})\
            .configure_logging(logging.DEBUG)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 5,
                "max_attempts": 4
            })\
            .build()

        self.reconnect_test(connection)
