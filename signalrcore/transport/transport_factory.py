from .base_transport import BaseTransport
from .websockets.websocket_transport import WebsocketTransport
from .sse.sse_transport import SSETransport
from .long_polling.long_polling_transport import LongPollingTransport
from ..hub.negotiation import NegotiateResponse
from typing import Optional
from ..types import HttpTransportType


TRANSPORTS = {
    HttpTransportType.web_sockets: WebsocketTransport,
    HttpTransportType.server_sent_events: SSETransport,
    HttpTransportType.long_polling: LongPollingTransport
}


def select_transport_type(
        negotiate_response: NegotiateResponse,
        preferred_transport: Optional[HttpTransportType]
        ) -> HttpTransportType:
    """Chooses the transport to use from the negotiate response.

    Shared by the sync and asyncio factories.
    """
    names = [
        available.transport
        for available in negotiate_response.available_transports
    ]

    if preferred_transport in names:
        return preferred_transport

    # Fallbacks
    if HttpTransportType.web_sockets in names:
        return HttpTransportType.web_sockets

    if HttpTransportType.server_sent_events in names:  # pragma no cover
        return HttpTransportType.server_sent_events

    if HttpTransportType.long_polling in names:
        return HttpTransportType.long_polling

    raise RuntimeError(
        f"Invalid transport types received {names}")  # pragma no cover


class TransportFactory(object):
    def create(
            negotiate_response: NegotiateResponse,
            preferred_transport: Optional[HttpTransportType],
            **kwargs) -> BaseTransport:

        transport_type = select_transport_type(
            negotiate_response, preferred_transport)

        if transport_type == preferred_transport:
            return TRANSPORTS[transport_type](**kwargs)

        # Fallbacks are resolved at call time so the module attributes
        # stay patchable.
        transports = {
            HttpTransportType.web_sockets: WebsocketTransport,
            HttpTransportType.server_sent_events: SSETransport,
            HttpTransportType.long_polling: LongPollingTransport
        }

        return transports[transport_type](**kwargs)
