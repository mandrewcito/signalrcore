import os
import unittest
import logging
import time
import uuid

from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder
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


class TestSendNoSslMethod(TestSendMethod):
    server_url = Urls.server_url_no_ssl