import os
import unittest
import logging
import time
import threading
import uuid

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.subject import Subject
from test.base_test_case import BaseTestCase, Urls

class TestClientStreamMethod(BaseTestCase):
    send_callback_received = threading.Lock()
    
    def setUp(self):
        pass

    def tearDown(self):
        pass
    
    def on_close(self):
        self.send_callback_received.release()

    def test_open_close(self):
        self.connection = self.get_connection()

        self.connection.start()
        
        while not self.connected:
            time.sleep(0.1)

        self.assertTrue(self.send_callback_received.acquire())
        
        self.connection.stop()
        
        self.assertTrue(self.send_callback_received.acquire(timeout=15))

        self.send_callback_received.release()
