from .base_transport import BaseTransport
from .websockets.websocket_transport import WebsocketTransport
from .sse.sse_transport import SSETransport
from ..hub.negotiation import AvailableTransport
from typing import List


class TransportFactory(object):
    def create(
            available_transports: List[AvailableTransport],
            **kwargs) -> BaseTransport:
        names = list(map(lambda x: x.transport, available_transports))

        if "WebSockets" in names:
            return WebsocketTransport(**kwargs)

        if "ServerSentEvents" in names:
            return SSETransport(**kwargs)
