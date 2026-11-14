import unittest

from signalrcore.hub.negotiation import AvailableTransport, NegotiateResponse
from signalrcore.protocol.protocol_factory import HANDSHAKE_VERSION, \
    ProtocolFactory
from signalrcore.types import HttpTransportType, HubProtocolEncoding


def negotiate_response(version):
    return NegotiateResponse(
        negotiate_version=version,
        connection_id="connection-id",
        connection_token="connection-token" if version >= 1 else None,
        access_token=None,
        url="wss://example.com/chat",
        available_transports=[
            AvailableTransport(
                transport=HttpTransportType.web_sockets,
                transfer_formats=[HubProtocolEncoding.text])
        ])


class ProtocolFactoryHandshakeVersionTest(unittest.TestCase):
    def test_version_zero_negotiation_uses_handshake_version_one(self):
        protocol = ProtocolFactory.create(
            HttpTransportType.web_sockets,
            HubProtocolEncoding.text,
            negotiate_response(0))

        self.assertEqual(protocol.version, 1)
        self.assertEqual(HANDSHAKE_VERSION, 1)
        self.assertEqual(protocol.handshake_message().version, 1)

    def test_version_one_negotiation_uses_handshake_version_one(self):
        protocol = ProtocolFactory.create(
            HttpTransportType.web_sockets,
            HubProtocolEncoding.text,
            negotiate_response(1))

        self.assertEqual(protocol.version, 1)

    def test_explicit_version_argument_is_ignored(self):
        protocol = ProtocolFactory.create(
            HttpTransportType.web_sockets,
            HubProtocolEncoding.text,
            negotiate_response(1),
            version=7)

        self.assertEqual(protocol.version, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
