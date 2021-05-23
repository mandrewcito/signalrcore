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
"""
class TestIntervalReconnectMethods(BaseTestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_reconnect_interval(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "interval",
                "intervals": [10, 5, 5, 45, 6, 7, 8, 9, 10],
                "keep_alive_interval": 5
            })\
            .build()
        self.reconnect_test(connection)
        
    def reconnect_test(self, connection):
        _lock = threading.Lock()
        
        self.assertTrue(_lock.acquire(timeout=10)) 

        connection.on_open(lambda: _lock.release())

        connection.start()

        self.assertTrue(_lock.acquire(timeout=10)) # Release on Open

        connection.send("DisconnectMe", [])

        self.assertTrue(_lock.acquire(timeout=20)) # released on open
        
        connection.send("SendMessage", ["self.username", "self.message"])

        _clock = threading.Lock()
        self.assertTrue(_clock.acquire(timeout=self.timeout))
        connection.on_close(lambda: _clock.release())
        connection.stop()
        self.assertTrue(_clock.acquire(timeout=self.timeout * 2))
        del _clock
        del connection
""""