import os
import unittest
import logging
import time
import uuid
import requests
from subprocess import Popen, PIPE
from signalrcore.hub_connection_builder import HubConnectionBuilder

from test.base_test_case import BaseTestCase, Urls

class TestSendAuthErrorMethod(BaseTestCase):
    server_url = Urls.server_url_ssl_auth
    login_url = Urls.login_url_ssl
    email = "test"
    password = "ff"
    received = False
    message = None

    def login(self):
        response = requests.post(
            self.login_url,
            json={
                "username": self.email,
                "password": self.password
                },verify=False)
        if response.status_code == 200:
            return response.json()["token"]
        raise requests.exceptions.ConnectionError()

    def setUp(self):
        pass

    def test_send(self):
        self.connection = HubConnectionBuilder()\
            .with_url(self.server_url,
            options={
                "verify_ssl": False,
                "access_token_factory": self.login,
            })\
            .configure_logging(logging.ERROR)\
            .build()
        self.connection.on_open(self.on_open)
        self.connection.on_close(self.on_close)
        self.assertRaises(requests.exceptions.ConnectionError, lambda :self.connection.start())
        
class TestSendNoSslAuthMethod(TestSendAuthErrorMethod):
    server_url = Urls.server_url_no_ssl_auth
    login_url = Urls.login_url_no_ssl
