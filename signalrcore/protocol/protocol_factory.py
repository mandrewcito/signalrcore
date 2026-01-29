from .base_hub_protocol import BaseHubProtocol
from .json_hub_protocol import JsonHubProtocol
from .messagepack_protocol import MessagePackHubProtocol

from typing import Optional
from ..types import HubProtocolEncoding
from ..hub.negotiation import NegotiateResponse, HttpTransportType
from ..helpers import ListHelpers


PROTOCOLS = {
    HubProtocolEncoding.text: JsonHubProtocol,
    HubProtocolEncoding.binary: MessagePackHubProtocol
}


class ProtocolFactory(object):
    def create(
            preferred_transport: Optional[HttpTransportType],
            preferred_protocol: Optional[HubProtocolEncoding],
            negotiate_response: NegotiateResponse,
            **kwargs) -> BaseHubProtocol:

        available_transports = negotiate_response.available_transports

        transports_map = ListHelpers.list_to_dict(
            available_transports,
            lambda x: x.transport)

        transport = transports_map.get(
            preferred_transport,
            available_transports[0]
        )

        protocols = transport.transfer_formats

        protocols_map = ListHelpers.list_to_dict(
            protocols,
            lambda x: x
        )

        protocol_key = protocols_map.get(
            preferred_protocol,
            protocols[0]
        )

        protocol = PROTOCOLS.get(protocol_key, JsonHubProtocol)

        return protocol(
            version=negotiate_response.negotiate_version,
            **kwargs)
