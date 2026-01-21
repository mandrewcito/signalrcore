from .base_transport import BaseTransport
from .websockets.websocket_transport import WebsocketTransport
from .sse.sse_transport import SSETransport
from ..hub.negotiation import AvailableTransport
from typing import List, Optional
from ..types import HttpTransportType


TRANSPORTS = {
    HttpTransportType.web_sockets: WebsocketTransport,
    HttpTransportType.server_sent_events: SSETransport
}


class TransportFactory(object):
    def create(
            available_transports: List[AvailableTransport],
            preferred_transport: Optional[HttpTransportType],
            **kwargs) -> BaseTransport:
        names = list(map(lambda x: x.transport, available_transports))

        if preferred_transport in names:
            return TRANSPORTS.get(preferred_transport)(**kwargs)

        # Fallbacks
        if HttpTransportType.web_sockets in names:
            return WebsocketTransport(**kwargs)

        if HttpTransportType.server_sent_events in names:
            return SSETransport(**kwargs)
