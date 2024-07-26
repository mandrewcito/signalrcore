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
    _locks = {} 

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_start(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .build()
        
        _lock = threading.Lock()
        self.assertTrue(_lock.acquire(timeout=30))
        

        connection.on_open(lambda: _lock.release())
        connection.on_close(lambda: _lock.release())
        
        result = connection.start()

        self.assertTrue(result)
        
        result = connection.start()
        
        self.assertFalse(result)
        
        connection.stop()
        del connection
        
    def test_open_close(self):
        connection = self.get_connection()

        identifier = str(uuid.uuid4())
        self._locks[identifier] = threading.Lock()

        connection.on_open(lambda: self._locks[identifier].release())
        connection.on_close(lambda: self._locks[identifier].release())

        self.assertTrue(self._locks[identifier].acquire())

        connection.start()

        self.assertTrue(self._locks[identifier].acquire())
        
        connection.stop()
        
        del self._locks[identifier]
        del connection