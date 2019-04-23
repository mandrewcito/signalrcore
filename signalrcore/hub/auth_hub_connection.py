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

        url = helpers.encode_connection_id(url, data["connectionId"])
        
        super(AuthHubConnection, self).__init__(url, protocol, headers=self.negotiate_headers)