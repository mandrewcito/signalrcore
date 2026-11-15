from typing import Optional

from ...hub.negotiation import NegotiateResponse
from ...transport.transport_factory import select_transport_type
from ...types import HttpTransportType
from .base_transport import AIOBaseTransport
from .long_polling.transport import AIOLongPollingTransport
from .sse.transport import AIOSSETransport
from .websockets.transport import AIOWebsocketTransport


TRANSPORTS = {
    HttpTransportType.web_sockets: AIOWebsocketTransport,
    HttpTransportType.server_sent_events: AIOSSETransport,
    HttpTransportType.long_polling: AIOLongPollingTransport
}


class AIOTransportFactory(object):
    def create(
            negotiate_response: NegotiateResponse,
            preferred_transport: Optional[HttpTransportType],
            **kwargs) -> AIOBaseTransport:

        transport_type = select_transport_type(
            negotiate_response, preferred_transport)

        # Resolved at call time so the module attributes stay patchable.
        transports = {
            HttpTransportType.web_sockets: AIOWebsocketTransport,
            HttpTransportType.server_sent_events: AIOSSETransport,
            HttpTransportType.long_polling: AIOLongPollingTransport
        }

        return transports[transport_type](**kwargs)
