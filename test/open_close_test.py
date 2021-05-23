from multiprocessing import connection
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

class TestOpenCloseMethod(BaseTestCase):    
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
        connection.on_open(lambda: _lock.release())
        
        self.assertTrue(_lock.acquire(timeout=30))
        result = connection.start()

        self.assertTrue(result)
        self.assertTrue(_lock.acquire(timeout=30))  # Released on open
        
        connection.on_open(None)
        result = connection.start()
        del _lock

        self.assertFalse(result)
        
        _lock = threading.Lock()
        self.assertTrue(_lock.acquire(timeout=30))
        connection.on_close(lambda: _lock.release())        
        connection.stop()
        self.assertTrue(_lock.acquire(timeout=30))
        del connection
        del _lock
        
    def test_open_close(self):
        connection = self.get_connection()
      
        _lock = threading.Lock()

        connection.on_open(lambda: _lock.release())
        connection.on_close(lambda: _lock.release())

        self.assertTrue(_lock.acquire())

        connection.start()

        self.assertTrue(_lock.acquire())
        
        connection.stop()
        
        self.assertTrue(_lock.acquire())

        del connection
        del _lock