from ..hub_connection_builder import HubConnectionBuilder
from .hub.aio_base_hub_connection import AIOBaseHubConnection
from .hub.aio_auth_hub_connection import AIOAuthHubConnection


class AIOHubConnectionBuilder(HubConnectionBuilder):
    def build(self):
        """Creates the connection hub

        Returns:
            [BaseHubConnection]: [connection SignalR object]
        """

        return AIOAuthHubConnection(
                headers=self.headers,
                auth_function=self.auth_function,
                url=self.hub_url,
                protocol=self.protocol,
                preferred_protocol=self.preferred_protocol,
                keep_alive_interval=self.keep_alive_interval,
                reconnection_handler=self.reconnection_handler,
                ssl_context=self.ssl_context,
                proxies=self.proxies,
                skip_negotiation=self.skip_negotiation,
                enable_trace=self.enable_trace,
                preferred_transport=self.transport)\
            if self.has_auth_configured else\
            AIOBaseHubConnection(
                url=self.hub_url,
                protocol=self.protocol,
                preferred_protocol=self.preferred_protocol,
                keep_alive_interval=self.keep_alive_interval,
                reconnection_handler=self.reconnection_handler,
                headers=self.headers,
                ssl_context=self.ssl_context,
                proxies=self.proxies,
                skip_negotiation=self.skip_negotiation,
                enable_trace=self.enable_trace,
                preferred_transport=self.transport)
