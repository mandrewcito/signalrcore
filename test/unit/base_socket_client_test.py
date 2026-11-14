import base64
import unittest
from unittest.mock import Mock, patch

from signalrcore.protocol.json_hub_protocol import JsonHubProtocol
from signalrcore.transport.sockets.base_socket_client import BaseSocketClient
from signalrcore.transport.sockets.errors \
    import NoHeaderException, SocketClosedError, SocketHandshakeError
from signalrcore.transport.websockets.websocket_transport import \
    WebsocketTransport

CREATE_CONNECTION = "signalrcore.transport.sockets." \
    "base_socket_client.socket.create_connection"


class FakeSocketClient(BaseSocketClient):
    def __init__(
            self,
            error=None,
            is_closing=False,
            url=None,
            proxies=None,
            ssl_context=None):
        super(FakeSocketClient, self).__init__(
            thread_name="fake socket client",
            success_status_code=b"101",
            url=url,
            proxies=proxies,
            ssl_context=ssl_context,
            on_open=self._noop,
            on_close=self._on_close,
            on_error=self._on_error)
        self.error = error
        self.is_closing = is_closing
        self.running = True
        self.closed = False
        self.received_error = None

    def _noop(self):
        pass

    def _on_close(self):
        self.closed = True

    def _on_error(self, error):
        self.received_error = error

    def _recv_frame(self):
        raise self.error


class SocketErrorClassificationTest(unittest.TestCase):
    def run_client(self, error, is_closing=False):
        client = FakeSocketClient(error=error, is_closing=is_closing)
        client.run()
        return client

    def test_empty_response_closes_connection(self):
        client = self.run_client(NoHeaderException())

        self.assertTrue(client.closed)
        self.assertIsNone(client.received_error)

    def test_server_closed_socket_closes_connection(self):
        client = self.run_client(SocketClosedError())

        self.assertTrue(client.closed)
        self.assertIsNone(client.received_error)

    def test_closed_file_descriptor_closes_connection(self):
        client = self.run_client(OSError(9, "Bad file descriptor"))

        self.assertTrue(client.closed)
        self.assertIsNone(client.received_error)

    def test_empty_response_while_closing_is_ignored(self):
        client = self.run_client(NoHeaderException(), is_closing=True)

        self.assertFalse(client.closed)
        self.assertIsNone(client.received_error)

    def test_closed_file_descriptor_while_closing_is_ignored(self):
        client = self.run_client(
            OSError(9, "Bad file descriptor"), is_closing=True)

        self.assertFalse(client.closed)
        self.assertIsNone(client.received_error)

    def test_other_errors_are_reported(self):
        error = OSError(5, "Input/output error")

        client = self.run_client(error)

        self.assertFalse(client.closed)
        self.assertIs(client.received_error, error)


class ProxySocketCreationTest(unittest.TestCase):
    def setUp(self):
        self.ssl_context = Mock()
        self.wrapped_socket = Mock()
        self.ssl_context.wrap_socket.return_value = self.wrapped_socket

        self.raw_socket = Mock()
        self.raw_socket.recv.return_value = \
            b"HTTP/1.1 200 Connection established\r\n\r\n"

    def build_client(self, url, proxies):
        return FakeSocketClient(
            url=url,
            proxies=proxies,
            ssl_context=self.ssl_context)

    def sent_request(self):
        return self.raw_socket.sendall.call_args[0][0].decode("utf-8")

    @patch(CREATE_CONNECTION)
    def test_direct_secure_connection_wraps_socket(self, create_connection):
        create_connection.return_value = self.raw_socket
        client = self.build_client("wss://example.com/chat", None)

        sock = client.create_socket()

        create_connection.assert_called_once_with(("example.com", 443))
        self.ssl_context.wrap_socket.assert_called_once_with(
            self.raw_socket, server_hostname="example.com")
        self.assertIs(sock, self.wrapped_socket)

    @patch(CREATE_CONNECTION)
    def test_direct_insecure_connection_does_not_wrap_socket(
            self, create_connection):
        create_connection.return_value = self.raw_socket
        client = self.build_client("ws://example.com/chat", None)

        sock = client.create_socket()

        create_connection.assert_called_once_with(("example.com", 80))
        self.ssl_context.wrap_socket.assert_not_called()
        self.assertIs(sock, self.raw_socket)

    @patch(CREATE_CONNECTION)
    def test_secure_connection_tunnels_through_proxy(
            self, create_connection):
        create_connection.return_value = self.raw_socket
        client = self.build_client(
            "wss://example.com/chat",
            {"https": "http://proxy:8080"})

        sock = client.create_socket()

        create_connection.assert_called_once_with(("proxy", 8080))
        request = self.sent_request()
        self.assertIn("CONNECT example.com:443 HTTP/1.1", request)
        self.assertIn("Host: example.com:443", request)
        self.ssl_context.wrap_socket.assert_called_once_with(
            self.raw_socket, server_hostname="example.com")
        self.assertIs(sock, self.wrapped_socket)

    @patch(CREATE_CONNECTION)
    def test_proxy_credentials_are_sent(self, create_connection):
        create_connection.return_value = self.raw_socket
        client = self.build_client(
            "wss://example.com/chat",
            {"https": "http://user:pass@proxy:8080"})

        client.create_socket()

        credentials = base64.b64encode(
            b"user:pass").decode("utf-8")
        self.assertIn(
            "Proxy-Authorization: Basic {0}".format(credentials),
            self.sent_request())

    @patch(CREATE_CONNECTION)
    def test_proxy_rejection_raises_handshake_error(
            self, create_connection):
        self.raw_socket.recv.return_value = \
            b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n"
        create_connection.return_value = self.raw_socket
        client = self.build_client(
            "wss://example.com/chat",
            {"https": "http://proxy:8080"})

        self.assertRaises(SocketHandshakeError, client.create_socket)
        self.ssl_context.wrap_socket.assert_not_called()

    @patch(CREATE_CONNECTION)
    def test_proxy_closed_during_tunnel_raises_handshake_error(
            self, create_connection):
        self.raw_socket.recv.return_value = b""
        create_connection.return_value = self.raw_socket
        client = self.build_client(
            "wss://example.com/chat",
            {"https": "http://proxy:8080"})

        self.assertRaises(SocketHandshakeError, client.create_socket)
        self.ssl_context.wrap_socket.assert_not_called()

    @patch(CREATE_CONNECTION)
    def test_insecure_connection_does_not_tunnel_through_proxy(
            self, create_connection):
        create_connection.return_value = self.raw_socket
        client = self.build_client(
            "ws://example.com/chat",
            {"http": "http://proxy:8080"})

        sock = client.create_socket()

        create_connection.assert_called_once_with(("proxy", 8080))
        self.raw_socket.sendall.assert_not_called()
        self.ssl_context.wrap_socket.assert_not_called()
        self.assertIs(sock, self.raw_socket)


class WebsocketTransportProxyTest(unittest.TestCase):
    def test_websocket_transport_forwards_proxies(self):
        proxies = {"https": "http://proxy:8080"}
        transport = WebsocketTransport(
            url="wss://example.com/chat",
            protocol=JsonHubProtocol(),
            proxies=proxies)

        client = transport.create_client()

        self.assertEqual(client.proxies, proxies)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
