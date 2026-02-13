import threading
import ssl
from urllib.error import URLError
from ...base_test_case import BaseTestCase, LOCK_TIMEOUT
from signalrcore.hub_connection_builder import HubConnectionBuilder

LOCKS = {}

MY_CA_FILE_PATH = "test/resources/certificates/ca.crt"


class CustomSslContextWebSocketTests(BaseTestCase):
    def get_connection(self, msgpack=False, options=None):
        if options is None:
            options = {
                "ssl_context": ssl._create_unverified_context()
            }
        return super().get_connection(msgpack, options=options)

    def test_send_message(self):
        identifier = self.get_random_id()
        LOCKS[identifier] = threading.Lock()
        self.message = "new message {0}".format(identifier)
        self.username = "mandrewcito"

        def release(msg):
            global LOCKS
            self.logger.debug(msg)
            if identifier in msg[1]:
                LOCKS[identifier].release()

        self.connection.on("ReceiveMessage", release)

        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))
        self.connection.send("SendMessage", [self.username, self.message])
        self.assertTrue(LOCKS[identifier].acquire(timeout=LOCK_TIMEOUT))
        del LOCKS[identifier]


class CustomSslContextServerSentEventsTests(CustomSslContextWebSocketTests):
    def get_connection(self, msgpack=False):
        context = ssl._create_unverified_context()
        return super().get_connection_sse(msgpack, options={
            "ssl_context": context
        })


class CustomSslContextLongPollingTests(CustomSslContextWebSocketTests):
    def get_connection(self, msgpack=False):
        context = ssl._create_unverified_context()
        return super().get_connection_long_polling(
            msgpack,
            False,
            options={
                "ssl_context": context
                })


class CustomSslContextWebSocketWithCertTests(CustomSslContextWebSocketTests):
    def get_connection(self, msgpack=False):
        context = ssl.create_default_context(
            cafile=MY_CA_FILE_PATH
        )

        return super().get_connection(msgpack, options={
            "ssl_context": context
        })


class CustomSslContextServerSentEventsWithCertTests(
        CustomSslContextWebSocketTests):
    def get_connection(self, msgpack=False):
        context = ssl.create_default_context(
            cafile=MY_CA_FILE_PATH
        )

        return super().get_connection_sse(msgpack, options={
            "ssl_context": context
        })


class CustomSslContextLongPollingWithCertTests(
        CustomSslContextWebSocketTests):
    def get_connection(self, msgpack=False):
        context = ssl.create_default_context(
            cafile=MY_CA_FILE_PATH
        )

        return super().get_connection_long_polling(msgpack, options={
            "ssl_context": context
        })


class CustomSslContextErrorTests(BaseTestCase):
    def tearDown(self):  # pragma: no cover
        pass

    def setUp(self):  # pragma: no cover
        pass

    def test_configure_default_cert_error(self):
        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                    "ssl_context": ssl.create_default_context()
                })\
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
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)

        self.assertRaises(
            URLError,
            hub.start
        )
