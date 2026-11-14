import unittest
from unittest.mock import patch

from signalrcore.hub.negotiation import AvailableTransport, NegotiateResponse
from signalrcore.transport.long_polling.long_polling_transport import\
    LongPollingTransport
from signalrcore.transport.transport_factory import TransportFactory
from signalrcore.types import HttpTransportType, HubProtocolEncoding


FACTORY = "signalrcore.transport.transport_factory"


def negotiate_response(*transports):
    return NegotiateResponse(
        negotiate_version=1,
        connection_id="connection-id",
        connection_token=None,
        access_token=None,
        url="ws://example.com/chat",
        available_transports=[
            AvailableTransport(
                transport=transport,
                transfer_formats=[HubProtocolEncoding.text])
            for transport in transports
        ])


class TransportFactoryFallbackTest(unittest.TestCase):
    def setUp(self):
        self.kwargs = {"url": "ws://example.com/chat"}

    @patch(FACTORY + ".LongPollingTransport")
    @patch(FACTORY + ".SSETransport")
    @patch(FACTORY + ".WebsocketTransport")
    def test_long_polling_only_server_uses_long_polling(
            self, websockets, sse, long_polling):
        expected = long_polling.return_value

        result = TransportFactory.create(
            negotiate_response(HttpTransportType.long_polling),
            None,
            **self.kwargs)

        self.assertIs(result, expected)
        long_polling.assert_called_once_with(**self.kwargs)
        sse.assert_not_called()
        websockets.assert_not_called()

    @patch(FACTORY + ".LongPollingTransport")
    @patch(FACTORY + ".SSETransport")
    @patch(FACTORY + ".WebsocketTransport")
    def test_sse_only_server_uses_sse(self, websockets, sse, long_polling):
        expected = sse.return_value

        result = TransportFactory.create(
            negotiate_response(HttpTransportType.server_sent_events),
            None,
            **self.kwargs)

        self.assertIs(result, expected)
        sse.assert_called_once_with(**self.kwargs)
        long_polling.assert_not_called()

    @patch(FACTORY + ".LongPollingTransport")
    @patch(FACTORY + ".SSETransport")
    @patch(FACTORY + ".WebsocketTransport")
    def test_websockets_are_preferred_over_other_transports(
            self, websockets, sse, long_polling):
        expected = websockets.return_value

        result = TransportFactory.create(
            negotiate_response(
                HttpTransportType.long_polling,
                HttpTransportType.server_sent_events,
                HttpTransportType.web_sockets),
            None,
            **self.kwargs)

        self.assertIs(result, expected)
        websockets.assert_called_once_with(**self.kwargs)

    @patch(FACTORY + ".LongPollingTransport")
    @patch(FACTORY + ".SSETransport")
    @patch(FACTORY + ".WebsocketTransport")
    def test_preferred_transport_wins(self, websockets, sse, long_polling):
        result = TransportFactory.create(
            negotiate_response(
                HttpTransportType.web_sockets,
                HttpTransportType.long_polling),
            HttpTransportType.long_polling,
            **self.kwargs)

        self.assertIsInstance(result, LongPollingTransport)
        long_polling.assert_not_called()

    def test_no_available_transports_raises(self):
        with self.assertRaises(RuntimeError):
            TransportFactory.create(negotiate_response(), None, **self.kwargs)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
