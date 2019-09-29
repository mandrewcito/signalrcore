import os
import unittest
import logging
import time
import uuid
import requests
from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder

class TestSendAuthMethod(unittest.TestCase):
    container_id = "netcore_chat_app"
    connection = None
    server_url = "ws://localhost:83/hubs/chat?myid=234"
    login_url = "http://localhost:83/account/token"
    email = "MM@GMAIL.COM"
    passowrd ="DDbc123._"
    received = False
    connected = False
    message = None

    def login(self):
        response = requests.post(
            self.login_url,
            data={
                "email": self.email,
                "password": self.passowrd
                })
        return response.json()["token"]

    def setUp(self):
        self.connection = HubConnectionBuilder()\
            .with_url(self.server_url,
            options={
                "access_token_factory": self.login
            })\
            .configure_logging(logging.DEBUG)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            }).build()
        self.connection.on("ReceiveChatMessage", self.receive_message)
        self.connection.on_open(self.on_open)
        self.connection.on_close(self.on_close)
        self.connection.start()
        while not self.connected:
            time.sleep(0.1)

    def tearDown(self):
        self.connection.stop()

    def on_open(self):
        self.connected = True

    def on_close(self):
        self.connected = False

    def receive_message(self, args):
        self.assertEqual(args[0], "{0}: {1}".format(self.email,self.message))
        self.received = True

    def test_send(self):
        self.message = "new message {0}".format(uuid.uuid4())
        self.username = "mandrewcito"
        time.sleep(1)
        self.received = False
        self.connection.send("Send", [self.message])
        while not self.received:
            time.sleep(0.1)
        

