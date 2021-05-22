from multiprocessing import connection
import unittest
import logging
import threading
import time
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
from signalrcore.transport.websockets.connection import ConnectionState

class Urls:
    server_url_no_ssl = "ws://localhost:5000/chatHub"
    server_url_ssl = "wss://localhost:5001/chatHub"
    server_url_no_ssl_auth = "ws://localhost:5000/authHub"
    server_url_ssl_auth = "wss://localhost:5001/authHub"
    login_url_ssl =  "https://localhost:5001/users/authenticate"
    login_url_no_ssl =  "http://localhost:5000/users/authenticate"

class InternalTestCase(unittest.TestCase):
    connection = None
    timeout = 10

    def get_connection(self):
        raise NotImplementedError()

    def start(self):
        _lock = threading.Lock()
        _lock.acquire(timeout=self.timeout)
        self.connection.on_open(lambda: _lock.release())
        self.connection.start()
        _lock.acquire(timeout=self.timeout)
        del _lock

    def setUp(self):
        self.connection = self.get_connection()
        self.start()

    def tearDown(self):
        if self.connection.transport.state == ConnectionState.connected\
                or self.connection.transport.state == ConnectionState.connecting:
            self.stop()
        del self.connection
        
    def stop(self):
        _lock = threading.Lock()
        self.connection.on_close(lambda: _lock.release())
        _lock.acquire(timeout=self.timeout)
        self.connection.stop()
        _lock.acquire(timeout=self.timeout)
        
class BaseTestCase(InternalTestCase):
    server_url = Urls.server_url_ssl

    def get_connection(self, msgpack=False):
        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })

        if msgpack:
            builder.with_hub_protocol(MessagePackHubProtocol())

        hub = builder.build()
        return hub