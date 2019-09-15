import os
import unittest
import logging
import time
import uuid

from signalrcore.hub_connection_builder import HubConnectionBuilder

class TestSendMethod(unittest.TestCase):
    container_id = "netcore_chat_app"
    connection = None
    server_url = "ws://localhost/chatHub"
    received = False
    connected = False
    message = None
    def setUp(self):
        self.connection = HubConnectionBuilder()\
            .with_url(self.server_url)\
            .configure_logging(logging.DEBUG)\
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

    def tearDown(self):
        self.connection.stop()

    @classmethod
    def setUpClass(cls):
        #os.system("docker run --name {0} --rm -d -p 80:80/tcp chatsample:latest".format(cls.container_id))
        pass

    @classmethod
    def tearDownClass(cls):
        #os.system("sudo docker stop {0}".format(cls.container_id))
        pass
    
    def on_open(self):
        self.connected = True

    def on_close(self):
        self.connected = False

    def receive_message(self, args):
        self.assertEqual(args[1], self.message)
        self.received = True

    def test_send(self):
        self.message = "new message {0}".format(uuid.uuid4())
        self.username = "mandrewcito"
        self.received = False
        self.connection.send("SendMessage", [self.username, self.message])
        while not self.received:
            time.sleep(0.1)

