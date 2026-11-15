from ...helpers import Helpers
from ..utils import maybe_await
from .aio_base_hub_connection import AIOBaseHubConnection


class AIOAuthHubConnection(AIOBaseHubConnection):
    """Asyncio hub connection that fetches a bearer token before connecting."""

    def __init__(self, auth_function, headers=None, **kwargs):
        if headers is None:
            self.headers = dict()
        else:
            self.headers = headers

        self.auth_function = auth_function

        super(AIOAuthHubConnection, self).__init__(headers=headers, **kwargs)

    async def start(self) -> bool:
        """Fetches the access token and starts the connection.

        The auth function may be a plain function or a coroutine function.

        Returns:
            bool: True if connection starts successfully, False if it is
            already connected.
        """
        try:
            Helpers.get_logger().debug("Starting connection ...")
            self.token = await maybe_await(self.auth_function())
            Helpers.get_logger()\
                .debug("auth function result {0}".format(self.token))
            self.headers["Authorization"] = "Bearer " + self.token
            return await super(AIOAuthHubConnection, self).start()
        except Exception as ex:
            Helpers.get_logger().error(
                "Error starting connection: {0}".format(ex))
            raise ex
