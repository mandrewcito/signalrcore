import unittest
import logging
import time
import sys
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
from signalrcore.types import HttpTransportType


class Urls:
    server_url_no_ssl = "ws://localhost:5000/chatHub"
    server_url_ssl = "wss://localhost:5001/chatHub"

    server_url_http_no_ssl = "http://localhost:5000/chatHub"
    server_url_http_ssl = "https://localhost:5001/chatHub"

    server_url_no_ssl_auth = "ws://localhost:5000/authHub"
    server_url_ssl_auth = "wss://localhost:5001/authHub"

    login_url_ssl = "https://localhost:5001/users/authenticate"
    login_url_no_ssl = "http://localhost:5000/users/authenticate"

    @staticmethod
    def ws_to_http(url: str) -> str:
        return url\
            .replace("wss://", "https://")\
            .replace("ws://", "http://")


class InternalTestCase(unittest.TestCase):
    connection = None
    connected = False

    def get_connection(self):
        raise NotImplementedError()

    def setUp(self):
        self.connection = self.get_connection()
        self.connection.start()

        t0 = time.time()

        while not self.connected:
            time.sleep(0.1)
            if time.time() - t0 > 20:
                raise TimeoutError("TIMEOUT ")

    def tearDown(self):
        self.connection.stop()

        t0 = time.time()

        while self.connected:
            time.sleep(0.1)
            if time.time() - t0 > 20:
                raise TimeoutError("TIMEOUT Closing connection")

        del self.connection

    def on_open(self):
        self.connected = True

    def on_close(self):
        self.connected = False


class BaseTestCase(InternalTestCase):
    server_url = Urls.server_url_ssl

    def get_connection(self, msgpack=False):
        is_debug = "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

        enable_trace = is_debug
        log_level = logging.DEBUG\
            if is_debug else logging.ERROR

        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(log_level, socket_trace=enable_trace)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })

        if msgpack:
            builder.with_hub_protocol(MessagePackHubProtocol())

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def get_connection_sse(self, reconnection=False):
        is_debug = "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

        enable_trace = is_debug
        log_level = logging.DEBUG\
            if is_debug else logging.ERROR

        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.server_sent_events
                })\
            .configure_logging(log_level, socket_trace=enable_trace)

        if reconnection:
            builder\
                .with_automatic_reconnect({
                    "type": "raw",
                    "keep_alive_interval": 10,
                    "reconnect_interval": 5,
                    "max_attempts": 5
                })

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def get_connection_long_polling(self, reconnection=False, msgpack=False):
        is_debug = "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

        enable_trace = is_debug
        log_level = logging.DEBUG\
            if is_debug else logging.ERROR

        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.long_polling
                })\
            .configure_logging(log_level, socket_trace=enable_trace)

        if reconnection:
            builder\
                .with_automatic_reconnect({
                    "type": "raw",
                    "keep_alive_interval": 10,
                    "reconnect_interval": 5,
                    "max_attempts": 5
                })

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub
