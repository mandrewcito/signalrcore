import requests
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
        Helpers.get_logger().debug("Negotiate url:{0}".format(negotiate_url))

        response = requests.post(negotiate_url, headers=self.headers, verify=self.verify_ssl)
        Helpers.get_logger().debug("Response status code{0}".format(response.status_code))

        if response.status_code != 200:
            raise HubError(response.status_code) if response.status_code != 401 else UnAuthorizedHubError()
        data = response.json()
        if "connectionId" in data.keys():
            self.url = Helpers.encode_connection_id(self.url, data["connectionId"])
        
        # Azure
        if 'url' in data.keys() and 'accessToken' in data.keys():
            Helpers.get_logger().debug("Azure url, reformat headers, token and url {0}".format(data))
            self.url = data["url"] if data["url"].startswith("ws") else Helpers.http_to_websocket(data["url"])
            self.token = data["accessToken"]
            self.headers = {"Authorization": "Bearer " + self.token}

    def start(self):
        try:
            Helpers.get_logger().debug("Starting connection ...")
            self.token = self.auth_function()
            Helpers.get_logger().debug("auth function result {0}".format(self.token))
            self.headers = {
                "Authorization": "Bearer " + self.token
            }

            self.negotiate()
            super(AuthHubConnection, self).start()
        except Exception as ex:
            Helpers.get_logger().error(self.__class__.__name__)
            Helpers.get_logger().error(str(ex))
            raise ex

