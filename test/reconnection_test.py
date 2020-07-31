import os
import unittest
import logging
import time
import uuid
import threading

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder, HubConnectionError
from test.base_test_case import BaseTestCase, Urls

class TestReconnectMethods(BaseTestCase):
    def test_reconnect_interval_config(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "interval",
                "intervals": [1, 2, 4, 45, 6, 7, 8, 9, 10]
            })\
            .build()
        connection.on_open(self.on_open)
        connection.on_close(self.on_close)
        connection.start()
        
        while not self.connected:
            time.sleep(0.1)

        self.assertTrue(self.send_callback_received.acquire())
        
        connection.stop()
        
        self.assertTrue(self.send_callback_received.acquire(timeout=5))

    def tearDown(self):
        pass

    def setUp(self):
        self.send_callback_received = threading.Lock()

    def on_close(self):
        self.send_callback_received.release()


class TestSendNoSslMethod(TestReconnectMethods):
    server_url = Urls.server_url_no_ssl

