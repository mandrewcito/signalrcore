import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
from signalrcore.transport.long_polling.long_polling_client import\
    LongPollingBinaryClient, LongPollingTextClient
from signalrcore.transport.long_polling.long_polling_transport import\
    LongPollingTransport

REQUEST = "signalrcore.transport.long_polling."\
    "long_polling_client.RequestHelpers.get"


class LongPollingClientAppendTest(unittest.TestCase):
    def setUp(self):
        self.client = LongPollingTextClient(url="")

    def test_append_returns_all_complete_messages(self):
        frame = b'{"type":1}\x1e{"type":3}\x1e{"type":6'

        messages = self.client._append(frame)

        self.assertEqual(
            messages,
            [b'{"type":1}', b'{"type":3}'])
        self.assertEqual(self.client._buffer, b'{"type":6')

    def test_append_returns_empty_list_without_complete_messages(self):
        messages = self.client._append(b'{"type":6')

        self.assertEqual(messages, [])
        self.assertEqual(self.client._buffer, b'{"type":6')

    def test_append_joins_partial_frames(self):
        self.assertEqual(self.client._append(b'{"type":1'), [])
        self.assertEqual(
            self.client._append(b'}\x1e'),
            [b'{"type":1}'])
        self.assertEqual(self.client._buffer, b"")


class LongPollingClientSelectionTest(unittest.TestCase):
    def test_messagepack_uses_binary_client(self):
        transport = LongPollingTransport(protocol=MessagePackHubProtocol())

        self.assertIs(transport._client_cls, LongPollingBinaryClient)

    def test_json_uses_text_client(self):
        transport = LongPollingTransport(protocol=JsonHubProtocol())

        self.assertIs(transport._client_cls, LongPollingTextClient)

    def test_explicit_is_binary_uses_binary_client(self):
        transport = LongPollingTransport(
            protocol=JsonHubProtocol(),
            is_binary=True)

        self.assertIs(transport._client_cls, LongPollingBinaryClient)


class LongPollingBinaryClientTest(unittest.TestCase):
    def test_binary_client_constructs(self):
        client = LongPollingBinaryClient(
            url="http://localhost:5000/chat",
            connection_id="id")

        self.assertEqual(client._receive_headers["Accept"], "binary")
        self.assertEqual(client.prepare_data(b"\x01\x02"), b"\x01\x02")


class LongPollingRecvFrameTest(unittest.TestCase):
    def setUp(self):
        self.client = LongPollingTextClient(
            url="http://localhost:5000/chat",
            connection_id="id")

    @staticmethod
    def response(status_code, content):
        response = Mock()
        response.status_code = status_code
        response.content = content
        return response

    @patch(REQUEST)
    def test_returns_content_on_200(self, get):
        get.return_value = self.response(200, b'{"type":6}\x1e')

        self.assertEqual(self.client._recv_frame(), b'{"type":6}\x1e')

    @patch(REQUEST)
    def test_204_raises_os_error(self, get):
        get.return_value = self.response(204, b"")

        self.assertRaises(OSError, self.client._recv_frame)

    @patch(REQUEST)
    def test_unexpected_status_raises_os_error(self, get):
        get.return_value = self.response(500, b"")

        self.assertRaises(OSError, self.client._recv_frame)

    @patch(REQUEST)
    def test_404_http_error_raises_os_error(self, get):
        get.side_effect = HTTPError(
            "http://localhost:5000/chat", 404, "Not Found", None, None)

        self.assertRaises(OSError, self.client._recv_frame)

    @patch(REQUEST)
    def test_500_http_error_is_propagated(self, get):
        get.side_effect = HTTPError(
            "http://localhost:5000/chat", 500, "Server Error", None, None)

        self.assertRaises(HTTPError, self.client._recv_frame)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
