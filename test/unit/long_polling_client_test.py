import threading
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
POST = "signalrcore.transport.long_polling."\
    "long_polling_client.RequestHelpers.post"
DELETE = "signalrcore.transport.long_polling."\
    "long_polling_client.RequestHelpers.delete"


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


class LongPollingTimeoutsTest(unittest.TestCase):
    def setUp(self):
        self.client = LongPollingTextClient(
            url="http://localhost:5000/chat",
            on_close=Mock())

    @staticmethod
    def response(status_code=200, content=b"", data=None):
        response = Mock()
        response.status_code = status_code
        response.content = content
        response.json.return_value = data if data is not None else {}
        return response

    @patch(REQUEST)
    def test_recv_frame_uses_finite_timeout(self, get):
        get.return_value = self.response(content=b'{"type":6}\x1e')

        self.client._recv_frame()

        self.assertEqual(get.call_args.kwargs["timeout"], self.client.timeout)
        self.assertIsNotNone(self.client.timeout)

    @patch(POST)
    def test_send_uses_finite_timeout(self, post):
        post.return_value = self.response()

        self.client.send("message")

        self.assertEqual(post.call_args.kwargs["timeout"], self.client.timeout)

    @patch(DELETE)
    def test_close_uses_finite_timeout(self, delete):
        delete.return_value = self.response()
        self.client._running = True

        self.client.close()

        self.assertEqual(
            delete.call_args.kwargs["timeout"], self.client.timeout)

    def test_timeout_is_configurable(self):
        client = LongPollingTextClient(
            url="http://localhost:5000/chat",
            timeout=12.5)

        self.assertEqual(client.timeout, 12.5)


class LongPollingDisposeTest(unittest.TestCase):
    def setUp(self):
        self.client = LongPollingTextClient(url="http://localhost:5000/chat")

    def test_dispose_stops_loop_before_joining(self):
        thread = Mock()
        thread.is_alive.return_value = False
        self.client._running = True
        self.client._thread = thread

        self.client.dispose(timeout=0.01)

        self.assertFalse(self.client._running)
        thread.join.assert_called_once_with(timeout=0.01)
        self.assertIsNone(self.client._thread)

    def test_dispose_does_not_block_when_thread_is_stuck(self):
        thread = Mock()
        thread.is_alive.return_value = True
        self.client._thread = thread

        self.client.dispose(timeout=0.01)

        thread.join.assert_called_once_with(timeout=0.01)
        self.assertIs(self.client._thread, thread)

    def test_dispose_from_receive_thread_does_not_join(self):
        thread = Mock()
        self.client._thread = thread
        current = Mock()
        current.name = self.client.thread_name

        with patch.object(threading, "current_thread", return_value=current):
            self.client.dispose()

        thread.join.assert_not_called()


class LongPollingCloseLockTest(unittest.TestCase):
    def setUp(self):
        self.client = LongPollingTextClient(
            url="http://localhost:5000/chat",
            on_close=Mock())
        self.client._running = True

    @patch(DELETE)
    def test_close_returns_without_releasing_unacquired_lock(self, delete):
        self.client._lock = Mock()
        self.client._lock.acquire.return_value = False

        self.client.close()

        delete.assert_not_called()
        self.client._lock.release.assert_not_called()

    @patch(DELETE)
    def test_close_releases_acquired_lock(self, delete):
        delete.return_value = Mock()
        delete.return_value.status_code = 200
        delete.return_value.json.return_value = {}
        self.client._lock = Mock()
        self.client._lock.acquire.return_value = True

        self.client.close()

        self.client._lock.release.assert_called_once()
        self.assertFalse(self.client.is_closing)


class LongPollingRunOnOpenTest(unittest.TestCase):
    def test_on_open_error_is_reported(self):
        error = ValueError("bad on_open")
        client = LongPollingTextClient(
            url="http://localhost:5000/chat",
            on_open=Mock(side_effect=error),
            on_error=Mock(),
            on_close=Mock())

        client.run()

        client.on_error.assert_called_once_with(error)
        client.on_close.assert_not_called()
        self.assertFalse(client._running)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
