import os
import unittest
import logging
import time
import sys
import uuid

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
from signalrcore.types import HttpTransportType
from signalrcore.helpers import Helpers

CONNECTION_TIMEOUT = 20
LOCK_TIMEOUT = 10

HOST_SIGNALR_HTTP = os.getenv("HOST_SIGNALR_HTTP", "localhost:5000")
HOST_SIGNALR_HTTPS = os.getenv("HOST_SIGNALR_HTTPS", "localhost:5001")
HOST_AZURE_FUNC_HTTP = os.getenv("HOST_AZURE_FUNC_HTTP", "localhost:7071")


class Urls:
    server_url_no_ssl = f"ws://{HOST_SIGNALR_HTTP}/chatHub"
    server_url_ssl = f"wss://{HOST_SIGNALR_HTTPS}/chatHub"

    server_url_http_no_ssl = f"http://{HOST_SIGNALR_HTTP}/chatHub"
    server_url_http_ssl = f"https://{HOST_SIGNALR_HTTPS}/chatHub"

    server_url_no_ssl_auth = f"ws://{HOST_SIGNALR_HTTP}/authHub"
    server_url_ssl_auth = f"wss://{HOST_SIGNALR_HTTPS}/authHub"

    login_url_ssl = f"https://{HOST_SIGNALR_HTTPS}/users/authenticate"
    login_url_no_ssl = f"http://{HOST_SIGNALR_HTTP}/users/authenticate"

    azure_func_url_no_ssl = f"http://{HOST_AZURE_FUNC_HTTP}/api/"

    @staticmethod
    def ws_to_http(url: str) -> str:
        return url\
            .replace("wss://", "https://")\
            .replace("ws://", "http://")


class InternalTestCase(unittest.TestCase):
    connection = None
    connected = False
    logger = Helpers.get_logger()

    def get_connection(self):
        raise NotImplementedError()  # pragma: no cover

    def setUp(self):
        self.connection = self.get_connection()
        self.connection.start()

        t0 = time.time()

        while not self.connected:
            time.sleep(0.1)
            if time.time() - t0 > CONNECTION_TIMEOUT:
                raise TimeoutError("TIMEOUT Opening connection")
                # pragma: no cover

    def tearDown(self):
        self.connection.stop()

        t0 = time.time()

        while self.connected:
            time.sleep(0.1)
            if time.time() - t0 > CONNECTION_TIMEOUT:
                raise TimeoutError("TIMEOUT Closing connection")
                # pragma: no cover
        del self.connection

    def on_open(self):
        self.connected = True

    def on_close(self):
        self.connected = False


class BaseTestCase(InternalTestCase):
    server_url = Urls.server_url_ssl

    def get_random_id(self) -> str:
        return str(uuid.uuid4())

    def is_debug(self) -> bool:
        return "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

    def get_log_level(self):
        return logging.DEBUG\
            if self.is_debug() else logging.ERROR

    def get_connection(self, msgpack=False):
        is_debug = "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

        enable_trace = is_debug
        log_level = self.get_log_level()

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
        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.server_sent_events
                })\
            .configure_logging(
                self.get_log_level(),
                socket_trace=self.is_debug())

        if reconnection:
            builder\
                .with_automatic_reconnect({
                    "type": "raw",
                    "keep_alive_interval": 10,
                    "reconnect_interval": 5,
                    "max_attempts": 5
                })
            # pragma: no cover

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def get_connection_long_polling(self, reconnection=False, msgpack=False):
        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options={
                "verify_ssl": False,
                "transport": HttpTransportType.long_polling
                })\
            .configure_logging(
                self.get_log_level(),
                socket_trace=self.is_debug())

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
