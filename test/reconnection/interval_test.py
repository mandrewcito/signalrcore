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

class TestIntervalReconnectMethods(BaseTestCase, TestMixin):
    def test_reconnect_interval(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "interval",
                "intervals": [1, 2, 4, 45, 6, 7, 8, 9, 10],
                "keep_alive_interval": 3
            })\
            .build()
        self.reconnect_test(connection)

    def tearDown(self):
        pass
    
    def setUp(self):
        pass