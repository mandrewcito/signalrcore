import requests

from urllib import parse

from .base_hub_connection import BaseHubConnection
from ..helpers import helpers

class AuthHubConnection(BaseHubConnection):
    def __init__(self, url, protocol, token, negotiate_headers):
        self.token = token
        self.negotiate_headers = negotiate_headers

        response = requests.post(helpers.get_negotiate_url(url), headers=self.negotiate_headers)
        data = response.json()

        self.url = helpers.encode_connection_id(url, data["connectionId"])
        
        super(AuthHubConnection, self).__init__(url, protocol, headers=self.negotiate_headers)

    def negotiate(self):
        response = requests.post(helpers.get_negotiate_url(self.url), headers=self.negotiate_headers)
        data = response.json()
        self.url = helpers.encode_connection_id(self.url, data["connectionId"])

    def start(self):
        try:
            self.negotiate()
            super(AuthHubConnection, self).start()
        except Exception as ex:
            self.reconnecting = False

    def on_close(self):
        self.logger.info("-- web socket close --")
        if self.reconnect:
            self.stop()
            self.negotiate()
            self.start()