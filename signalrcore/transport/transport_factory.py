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


class TransportFactory(object):
    def create(
            negotiate_response: NegotiateResponse,
            preferred_transport: Optional[HttpTransportType],
            **kwargs) -> BaseTransport:

        names = list(
            map(
                lambda x: x.transport,
                negotiate_response.available_transports))

        if preferred_transport in names:
            return TRANSPORTS.get(preferred_transport)(**kwargs)

        # Fallbacks
        if HttpTransportType.web_sockets in names:
            return WebsocketTransport(**kwargs)

        if HttpTransportType.server_sent_events in names:
            # pragma no cover
            return SSETransport(**kwargs)
            # pragma no cover

        if HttpTransportType.server_sent_events in names:
            # pragma no cover
            return LongPollingTransport(**kwargs)
            # pragma no cover

        raise RuntimeError(
            f"Invalid transport types received {names}")
        # pragma no cover
