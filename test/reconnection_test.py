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


class TestReconnectMethods(BaseTestCase):
    _locks = {}
    
    def receive_message(self, args):
        self.assertEqual(args[1], self.message)
        self.received = True

    def test_reconnect_interval_config(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "interval",
                "intervals": [1, 2, 4, 45, 6, 7, 8, 9, 10]
            })\
            .build()

        identifier = str(uuid.uuid4())
        self._locks[identifier] = threading.Lock()

        connection.on_open(lambda: self._locks[identifier].release())
        connection.on_close(lambda: self._locks[identifier].release())

        self.assertTrue(self._locks[identifier].acquire(timeout=10))

        connection.start()

        self.assertTrue(self._locks[identifier].acquire(timeout=10))

        connection.transport._ws.close()

        self.assertTrue(self._locks[identifier].acquire(timeout=10))
        connection.stop()

        del self._locks[identifier]
        del connection

    def test_reconnect_interval(self):
        self.reconnect_test({
            "type": "interval",
            "intervals": [1, 2, 4, 45, 6, 7, 8, 9, 10],
            "keep_alive_interval": 3
            })

    def test_no_reconnect(self):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .build()

        identifier = str(uuid.uuid4())
        self._locks[identifier] = threading.Lock()
        
        self._locks[identifier].acquire(timeout=10)

        connection.on_open(lambda: self._locks[identifier].release())
        connection.on_close(lambda: self._locks[identifier].release())

        connection.on("ReceiveMessage", lambda _: self._locks[identifier].release())

        connection.start()

        self.assertTrue(self._locks[identifier].acquire(timeout=10))  # Released on ReOpen
        
        connection.transport._ws.close()

        #self.assertFalse(self._locks[identifier].acquire(timeout=10))


        self.assertRaises(
            HubConnectionError,
            lambda: connection.send("DisconnectMe", []))

        connection.stop()
        del connection


    def reconnect_test(self, options):
        connection = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl": False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect(options)\
            .build()

        identifier = str(uuid.uuid4())        
        self._locks[identifier] = threading.Lock()
        
        connection.on_open(lambda: self._locks[identifier].release())
        connection.on_close(lambda: self._locks[identifier].release())
        

        self.assertTrue(self._locks[identifier].acquire(timeout=5)) # Release on Open
        connection.start()

        self.assertTrue(self._locks[identifier].acquire(timeout=5)) # released on close

        connection.transport._ws.close(status=1000, reason="Closed".encode("utf-8"))
        #connection.send("DisconnectMe", [])
        
        self.assertTrue(self._locks[identifier].acquire(timeout=5)) # released on open
        
        del self._locks[identifier]
        connection.stop()
        del connection

    def test_raw_reconnection(self):
        self.reconnect_test({
            "type": "raw",
            "keep_alive_interval": 10,
            "max_attempts": 4
        })

    def test_raw_handler(self):
        handler = RawReconnectionHandler(5, 10)
        attemp = 0

        while attemp <= 10:
            self.assertEqual(handler.next(), 5)
            attemp = attemp + 1

        self.assertRaises(ValueError, handler.next)

    def test_interval_handler(self):
        intervals = [1, 2, 4, 5, 6]
        handler = IntervalReconnectionHandler(intervals)
        for interval in intervals:
            self.assertEqual(handler.next(), interval)
        self.assertRaises(ValueError, handler.next)

    def tearDown(self):
        pass

    def setUp(self):
        pass
