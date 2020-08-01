from .base_hub_connection import BaseHubConnection
from ..helpers import Helpers


class AuthHubConnection(BaseHubConnection):
    def __init__(self, url, protocol, auth_function, keep_alive_interval=15, reconnection_handler=None,
                 headers={}, verify_ssl=False, skip_negotiation=False):
        self.headers = headers
        self.auth_function = auth_function
        super(AuthHubConnection, self).__init__(
            url,
            protocol,
            headers=headers,
            keep_alive_interval=keep_alive_interval,
            reconnection_handler=reconnection_handler,
            verify_ssl=verify_ssl,
            skip_negotiation=skip_negotiation)

    def start(self):
        try:
            Helpers.get_logger().debug("Starting connection ...")
            self.token = self.auth_function()
            Helpers.get_logger().debug("auth function result {0}".format(self.token))
            self.headers["Authorization"] = "Bearer " + self.token
            super(AuthHubConnection, self).start()
        except Exception as ex:
            Helpers.get_logger().warning(self.__class__.__name__)
            Helpers.get_logger().warning(str(ex))
            raise ex

