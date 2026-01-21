import logging
import threading
import uuid

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.types import HttpTransportType
from test.base_test_case import BaseTestCase

LOCKS = {}


class TesTransportSelection(BaseTestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_websockets(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.web_sockets})\
            .configure_logging(logging.ERROR)\
            .build()
        self._test_run(connection)

    def test_sse(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.server_sent_events})\
            .configure_logging(logging.ERROR)\
            .build()
        self._test_run(connection)

    def _test_run(self, connection):
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
