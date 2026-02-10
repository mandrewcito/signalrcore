from .aio_base_hub_connection import AIOBaseHubConnection


class AIOAuthHubConnection(AIOBaseHubConnection):
    def __init__(self, **kwargs):
        super(AIOAuthHubConnection).__init__(kwargs)
