import base64
import hashlib
import struct
import unittest
from unittest.mock import Mock

from signalrcore.transport.sockets.errors import SocketClosedError, \
    SocketHandshakeError
from signalrcore.transport.websockets.websocket_client import \
    WebSocketClient, MAX_PAYLOAD_SIZE, WEBSOCKET_GUID


def accept_for(key):
    return base64.b64encode(
        hashlib.sha1(
            (key + WEBSOCKET_GUID).encode("utf-8")
        ).digest()
    ).decode("utf-8")


class WebSocketHostHeaderTest(unittest.TestCase):
    def host_header(self, url):
        client = WebSocketClient(url=url)
        headers = client.get_socket_headers()
        return next(
            header for header in headers
            if header.startswith("Host: "))

    def test_non_default_port_is_kept(self):
        self.assertEqual(
            self.host_header("ws://localhost:5000/chat"),
            "Host: localhost:5000")

    def test_default_port_is_omitted_when_absent(self):
        self.assertEqual(
            self.host_header("ws://localhost/chat"),
            "Host: localhost")

    def test_ipv6_host_keeps_brackets(self):
        self.assertEqual(
            self.host_header("wss://[::1]:5000/chat"),
            "Host: [::1]:5000")

    def test_user_info_is_not_forwarded(self):
        self.assertEqual(
            self.host_header("ws://user:pass@localhost:5000/chat"),
            "Host: localhost:5000")


class WebSocketAcceptValidationTest(unittest.TestCase):
    def setUp(self):
        self.client = WebSocketClient(url="ws://localhost/chat")
        self.client.get_socket_headers()
        self.key = self.client._websocket_key

    def response(self, accept):
        return (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        ).encode("utf-8")

    def test_valid_accept_is_accepted(self):
        self.client.validate_handshake_response(
            self.response(accept_for(self.key)))

    def test_header_name_is_case_insensitive(self):
        response = self.response(accept_for(self.key)).replace(
            b"Sec-WebSocket-Accept", b"sec-websocket-accept")

        self.client.validate_handshake_response(response)

    def test_invalid_accept_is_rejected(self):
        with self.assertRaises(SocketHandshakeError):
            self.client.validate_handshake_response(
                self.response(accept_for("another key")))

    def test_missing_accept_is_rejected(self):
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "\r\n"
        ).encode("utf-8")

        with self.assertRaises(SocketHandshakeError):
            self.client.validate_handshake_response(response)

    def test_custom_key_from_headers_is_used(self):
        client = WebSocketClient(
            url="ws://localhost/chat",
            headers={"Sec-WebSocket-Key": "custom-key"})
        client.get_socket_headers()

        client.validate_handshake_response(
            self.response(accept_for("custom-key")))


class WebSocketControlFrameTest(unittest.TestCase):
    def setUp(self):
        self.client = WebSocketClient(url="ws://localhost/chat")
        self.client._send_control_frame = Mock()

    def read_frames(self, *frames):
        self.client._read_one_frame = Mock(side_effect=list(frames))
        return self.client._recv_frame()

    def test_ping_is_answered_with_pong(self):
        payload = self.read_frames(
            (True, 0x9, b"ping"),
            (True, 0x1, b"data"))

        self.assertEqual(payload, "data")
        self.client._send_control_frame.assert_called_once_with(
            0xA, b"ping")

    def test_pong_is_ignored(self):
        payload = self.read_frames(
            (True, 0xA, b""),
            (True, 0x1, b"data"))

        self.assertEqual(payload, "data")
        self.client._send_control_frame.assert_not_called()

    def test_close_frame_closes_connection(self):
        with self.assertRaises(SocketClosedError):
            self.read_frames((True, 0x8, b""))

    def test_fragments_are_joined(self):
        payload = self.read_frames(
            (False, 0x1, b"hel"),
            (True, 0x0, b"lo"))

        self.assertEqual(payload, "hello")

    def test_control_frame_between_fragments(self):
        payload = self.read_frames(
            (False, 0x1, b"hel"),
            (True, 0x9, b"ping"),
            (True, 0x0, b"lo"))

        self.assertEqual(payload, "hello")
        self.client._send_control_frame.assert_called_once_with(
            0xA, b"ping")

    def test_continuation_without_start_is_rejected(self):
        with self.assertRaises(SocketClosedError):
            self.read_frames((True, 0x0, b"orphan"))

        self.client._send_control_frame.assert_called_once_with(
            0x8, struct.pack(">H", 1002))

    def test_unknown_opcode_is_rejected(self):
        with self.assertRaises(SocketClosedError):
            self.read_frames((True, 0x3, b"unknown"))

        self.client._send_control_frame.assert_called_once_with(
            0x8, struct.pack(">H", 1002))


class WebSocketPayloadLimitTest(unittest.TestCase):
    def setUp(self):
        self.client = WebSocketClient(url="ws://localhost/chat")
        self.client._send_control_frame = Mock()

    def test_declared_payload_over_limit_is_rejected(self):
        header = bytes([0x81, 0x7F])
        self.client._recv_exactly = Mock(
            side_effect=[header, struct.pack(">Q", MAX_PAYLOAD_SIZE + 1)])

        with self.assertRaises(SocketClosedError):
            self.client._read_one_frame()

        self.client._send_control_frame.assert_called_once_with(
            0x8, struct.pack(">H", 1009))

    def test_fragments_over_limit_are_rejected(self):
        big_fragment = b"x" * MAX_PAYLOAD_SIZE
        self.client._read_one_frame = Mock(
            side_effect=[
                (False, 0x1, big_fragment),
                (True, 0x0, b"y"),
            ])

        with self.assertRaises(SocketClosedError):
            self.client._recv_frame()

        self.client._send_control_frame.assert_called_once_with(
            0x8, struct.pack(">H", 1009))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
