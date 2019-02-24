import requests

from .base_hub_connection import BaseHubConnection


class AuthHubConnection(BaseHubConnection):
    def __init__(self, url, protocol, token, negotiate_headers):
        self.token = token
        self.negotiate_headers = negotiate_headers
        negotiate_url = "https" + url[3:] if url.startswith("wss") else "http" + url[2:]
        negotiate_url += "/negotiate"
        response = requests.post(negotiate_url, headers=self.negotiate_headers)
        data = response.json()
        url = url + "?id={0}&access_token={1}".format(data["connectionId"], self.token)
        super(AuthHubConnection, self).__init__(url, protocol)
