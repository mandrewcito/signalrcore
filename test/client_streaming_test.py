import os
import unittest
import logging
import time
import uuid

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.subject import Subject
class TestSendMethod(unittest.TestCase):
    container_id = "netcore_stream_app"
    connection = None
    server_url = "wss://localhost:5001/chatHub"
    received = False
    connected = False
    items = list(range(0,10))

    def setUp(self):
        self.connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
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

    def test_stream(self):
        self.complete = False
        self.items = list(range(0,10))
        subject = Subject()
        self.connection.send("UploadStream", subject)
        while(len(self.items) > 0):
            subject.next(str(self.items.pop()))
        subject.complete()
        self.assertTrue(len(self.items) == 0)
