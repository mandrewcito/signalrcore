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
from .test_mixin import TestMixin

class TestIntervalConfigReconnectMethods(BaseTestCase, TestMixin):
    def test_reconnect_interval_config(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "interval",
                "intervals": [1, 2, 4, 45, 6, 7, 8, 9, 10]
            })\
            .build()
        _lock = threading.Lock()
        connection.on_open(lambda: _lock.release())
        self.assertTrue(_lock.acquire(timeout=10))

        connection.start()

        self.assertTrue(_lock.acquire(timeout=10))
        del _lock

        _lock = threading.Lock()
        connection.on_close(lambda: _lock.release())
        _lock.acquire(timeout=self.timeout)
        connection.stop()
        _lock.acquire(timeout=self.timeout)
        del _lock
    
    def tearDown(self):
        pass
    
    def setUp(self):
        pass
