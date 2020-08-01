import os
import unittest
import logging
import time
import uuid
import threading

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder, HubConnectionError
from test.base_test_case import BaseTestCase, Urls

class TestSendMethod(BaseTestCase):
    received = False
    message = None
    def setUp(self):
        self.connection = self.get_connection()
        self.connection.on("ReceiveMessage", self.receive_message)
        self.connection.start()
        while not self.connected:
            time.sleep(0.1)

    def receive_message(self, args):
        self.assertEqual(args[1], self.message)
        self.received = True


    def test_send_bad_args(self):
        class A():
            pass

        self.assertRaises(TypeError, lambda : self.connection.send("SendMessage", A()))

    def test_send(self):
        self.message = "new message {0}".format(uuid.uuid4())
        self.username = "mandrewcito"
        self.received = False
        self.connection.send("SendMessage", [self.username, self.message])
        t0 = time.time()
        while not self.received:
            time.sleep(0.1)
            if time.time() - t0 > 10:
                raise ValueError("TIMEOUT")

    def test_send_with_callback(self):
        self.message = "new message {0}".format(uuid.uuid4())
        self.username = "mandrewcito"
        self.received = False
        send_callback_received = threading.Lock()
        send_callback_received.acquire()
        self.connection.send("SendMessage", [self.username, self.message], lambda m: send_callback_received.release())
        if not send_callback_received.acquire(timeout=1):
            raise ValueError("CALLBACK NOT RECEIVED")


class TestSendNoSslMethod(TestSendMethod):
    server_url = Urls.server_url_no_ssl


class TestSendErrorMethod(BaseTestCase):
    received = False
    message = None
    def setUp(self):
        self.connection = self.get_connection()
        self.connection.on("ReceiveMessage", self.receive_message)

    def receive_message(self, args):
        self.assertEqual(args[1], self.message)
        self.received = True


    def test_send_with_error(self):
        self.message = "new message {0}".format(uuid.uuid4())
        self.username = "mandrewcito"

        self.assertRaises(HubConnectionError,lambda : self.connection.send("SendMessage", [self.username, self.message]))
        
        self.connection.start()
        while not self.connected:
            time.sleep(0.1)

        self.received = False
        self.connection.send("SendMessage", [self.username, self.message])        
        t0 = time.time()
        while not self.received:
            time.sleep(0.1)
            if time.time() - t0 > 10:
                raise ValueError("TIMEOUT")

class TestSendErrorNoSslMethod(TestSendErrorMethod):
    server_url = Urls.server_url_no_ssl
