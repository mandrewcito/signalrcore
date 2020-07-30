import os
import unittest
import logging
import time
import uuid
import requests
from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder

from base_test_case import Urls

class TestSendAuthMethod(unittest.TestCase):
    server_url = Urls.server_url_ssl_auth
    login_url = Urls.login_url_ssl
    email = "test"
    password = "test"
    received = False
    message = None
    connection = None
    connected = False

    def setUp(self):
        self.connection = self.get_connection()
        self.connection.start()
        t0 = time.time()
        while not self.connected:
            time.sleep(0.1)
            if time.time() - t0 > 20:
                raise ValueError("TIMEOUT ")

    def tearDown(self):
        self.connection.stop()

    def on_open(self):
        self.connected = True

    def on_close(self):
        self.connected = False

    def get_connection(self):
        hub = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
            .configure_logging(logging.WARNING)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })\
            .build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def login(self):
        response = requests.post(
            self.login_url,
            json={
                "username": self.email,
                "password": self.password
                },verify=False)
        return response.json()["token"]

    def setUp(self):
        self.connection = HubConnectionBuilder()\
            .with_url(self.server_url,
            options={
                "verify_ssl": False,
                "access_token_factory": self.login,
                "headers": {
                    "mycustomheader": "mycustomheadervalue"
                }
            })\
            .configure_logging(logging.WARNING)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            }).build()
        self.connection.on("ReceiveMessage", self.receive_message)
        self.connection.on_open(self.on_open)
        self.connection.on_close(self.on_close)
        self.connection.start()
        while not self.connected:
            time.sleep(0.1)

    def receive_message(self, args):
        self.assertEqual(args[0], self.message)
        self.received = True

    def test_send(self):
        self.message = "new message {0}".format(uuid.uuid4())
        self.username = "mandrewcito"
        time.sleep(1)
        self.received = False
        self.connection.send("SendMessage", [self.message])
        while not self.received:
            time.sleep(0.1)
        
class TestSendNoSslAuthMethod(TestSendAuthMethod):
    server_url = Urls.server_url_no_ssl_auth
    login_url = Urls.login_url_no_ssl
