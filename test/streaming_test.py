import os
import unittest
import logging
import time
import uuid

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder

class TestSendMethod(unittest.TestCase):
    container_id = "netcore_stream_app"
    connection = None
    server_url = "ws://localhost:82/streamHub"
    received = False
    connected = False
    items = list(range(0,10))

    def setUp(self):
        self.connection = HubConnectionBuilder()\
            .with_url(self.server_url)\
            .configure_logging(logging.DEBUG)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })\
            .build()
        self.connection.on_open(self.on_open)
        self.connection.on_close(self.on_close)
        self.connection.start()
        while not self.connected:
            time.sleep(0.1)

    def tearDown(self):
        self.connection.stop()

    def on_open(self):
        print("opene")
        self.connected = True

    def on_close(self):
        self.connected = False

    def on_complete(self, x):
        self.complete = True
    
    def on_error(self, x):
        pass

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
