import os
import unittest
import logging
import time
import uuid

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder
from base_test_case import Urls

class TestSendMethod(unittest.TestCase):
    server_url = Urls.server_url_ssl
    received = False
    items = list(range(0,10))
    connection = None
    connected = False

    def setUp(self):
        self.connection = self.get_connection()
        self.connection.start()
        t0 = time.time()
        while not self.connected:
            time.sleep(0.1)
            if time.time() - t0 > 20:
                raise ValueError("TIMEOUT ")

    def tearDown(self):
        self.connection.stop()

    def on_open(self):
        self.connected = True

    def on_close(self):
        self.connected = False

    def get_connection(self):
        hub = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
            .configure_logging(logging.WARNING)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })\
            .build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def on_complete(self, x):
        self.complete = True
    
    def on_error(self, x):
        raise ValueError(x)

    def on_next(self, x):
        item = self.items[0]
        self.items = self.items[1:]
        self.assertEqual(x, item)

    def test_stream(self):
        self.complete = False
        self.items = list(range(0,10))
        self.connection.stream(
            "Counter",
            [len(self.items), 500]).subscribe({
                "next": self.on_next,
                "complete": self.on_complete,
                "error": self.on_error
            })
        while not self.complete:
            time.sleep(0.1)

class TestSendNoSslMethod(TestSendMethod):
    server_url = Urls.server_url_no_ssl