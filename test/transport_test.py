import logging
import threading
import uuid

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.types import HttpTransportType
from test.base_test_case import BaseTestCase
from test.base_test_case import Urls

LOCKS = {}


class TesTransportSelection(BaseTestCase):

    def setUp(self):  # pragma: no cover
        pass

    def tearDown(self):  # pragma: no cover
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
            .with_url(Urls.ws_to_http(self.server_url), options={
                "verify_ssl": False,
                "transport": HttpTransportType.server_sent_events
                })\
            .configure_logging(logging.ERROR)\
            .build()
        self._test_run(connection)

    def test_long_polling(self):
        connection = HubConnectionBuilder()\
            .with_url(Urls.ws_to_http(self.server_url), options={
                "verify_ssl": False,
                "transport": HttpTransportType.long_polling
                })\
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

        result = connection.start()

        self.assertFalse(result)

        message = "new message {0}".format(uuid.uuid4())
        username = "mandrewcito"

        identifier2 = str(uuid.uuid4())
        LOCKS[identifier2] = threading.Lock()

        LOCKS[identifier2].acquire()
        uid = str(uuid.uuid4())

        def release(m):
            global LOCKS
            self.assertTrue(m.invocation_id, uid)
            LOCKS[identifier2].release()

        connection.send(
            "SendMessage",
            [username, message],
            release,
            invocation_id=uid)

        connection.stop()

        del LOCKS[identifier]
        del connection
