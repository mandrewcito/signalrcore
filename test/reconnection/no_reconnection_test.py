import os
import unittest
import logging
import time
import uuid
import threading

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.hub.errors import HubConnectionError
from test.base_test_case import BaseTestCase, Urls
from signalrcore.transport.websockets.reconnection import RawReconnectionHandler, IntervalReconnectionHandler

class TestNoReconnect(BaseTestCase):
    def tearDown(self):
        pass

    def setUp(self):
        pass

    def test_no_reconnect(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .build()

        _lock = threading.Lock()

        _lock.acquire(timeout=10)

        connection.on_open(lambda: _lock.release())

        connection.on("ReceiveMessage", lambda _: _lock.release())

        connection.start()

        self.assertTrue(_lock.acquire(timeout=10))  # Released on ReOpen
        connection.on_open(lambda: None)
        
        connection.send("DisconnectMe", [])
        
        time.sleep(10)

        self.assertRaises(
            HubConnectionError,
            lambda: connection.send("DisconnectMe", []))
        del _lock
        del connection
