import requests
import logging
from .base_hub_connection import BaseHubConnection
from .errors import UnAuthorizedHubError, HubError
from ..helpers import Helpers


class AuthHubConnection(BaseHubConnection):
    def __init__(self, url, protocol, auth_function, keep_alive_interval=15, reconnection_handler=None,
                 headers={}, verify_ssl=False):
        self.token = None
        self.headers = None

        self.auth_function = auth_function
        
        super(AuthHubConnection, self).__init__(
            url,
            protocol,
            headers=headers,
            keep_alive_interval=keep_alive_interval,
            reconnection_handler=reconnection_handler,
            verify_ssl=verify_ssl)

    def negotiate(self):
        negotiate_url = Helpers.get_negotiate_url(self.url)
        logging.debug("Negotiate url:" + negotiate_url)
        response = requests.post(negotiate_url, headers=self.headers, verify=self.verify_ssl)
        if response.status_code != 200:
            raise HubError(response.status_code) if response.status_code != 401 else UnAuthorizedHubError()
        data = response.json()
        self.url = Helpers.encode_connection_id(self.url, data["connectionId"])
        
        # Azure
        if 'url' in data.keys() and 'accessToken' in data.keys():
            self.url = data["url"]
            self.token = data["accessToken"]
            self.headers = {"Authorization": "Bearer " + self.token}

    def start(self, reconnect=False):
        self.token = self.auth_function()
        self.headers = {
            "Authorization": "Bearer " + self.token
        }
        self.negotiate()
        super(AuthHubConnection, self).start()
