import json
import unittest

import msgpack

from signalrcore.messages.ack_message import AckMessage
from signalrcore.messages.cancel_invocation_message import (
    CancelInvocationMessage,
)
from signalrcore.messages.close_message import CloseMessage
from signalrcore.messages.completion_message import (
    CompletionClientStreamMessage,
    CompletionMessage,
)
from signalrcore.messages.handshake.request import HandshakeRequestMessage
from signalrcore.messages.invocation_message import (
    InvocationClientStreamMessage,
    InvocationMessage,
)
from signalrcore.messages.ping_message import PingMessage
from signalrcore.messages.sequence_message import SequenceMessage
from signalrcore.messages.stream_invocation_message import (
    StreamInvocationMessage,
)
from signalrcore.messages.stream_item_message import StreamItemMessage
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol


class UnknownTypeMessage(object):
    """Stub message with an unknown type, used to hit the encode fallback."""

    class type(object):
        value = 99


class TestMessagePackHubProtocol(unittest.TestCase):
    def setUp(self):
        self.protocol = MessagePackHubProtocol()

    def round_trip(self, message):
        decoded = self.protocol.parse_messages(self.protocol.encode(message))
        self.assertEqual(len(decoded), 1)
        return decoded[0]

    def test_encode_decode_invocation(self):
        decoded = self.round_trip(
            InvocationMessage("invocation-id", "SendMessage", ["user", "msg"]))

        self.assertIsInstance(decoded, InvocationMessage)
        self.assertEqual(decoded.invocation_id, "invocation-id")
        self.assertEqual(decoded.target, "SendMessage")
        self.assertEqual(decoded.arguments, ["user", "msg"])

    def test_encode_decode_invocation_with_stream_ids(self):
        message = InvocationClientStreamMessage(
            ["stream-id"],
            "UploadStream",
            [],
            invocation_id="invocation-id")

        decoded = self.round_trip(message)

        self.assertIsInstance(decoded, InvocationClientStreamMessage)
        self.assertEqual(decoded.stream_ids, ["stream-id"])
        self.assertEqual(decoded.target, "UploadStream")

    def test_encode_decode_stream_item(self):
        decoded = self.round_trip(StreamItemMessage("invocation-id", 42))

        self.assertIsInstance(decoded, StreamItemMessage)
        self.assertEqual(decoded.invocation_id, "invocation-id")
        self.assertEqual(decoded.item, 42)

    def test_encode_decode_completion_void(self):
        decoded = self.round_trip(
            CompletionClientStreamMessage("invocation-id"))

        self.assertIsInstance(decoded, CompletionMessage)
        self.assertIsNone(decoded.result)
        self.assertIsNone(decoded.error)

    def test_encode_decode_completion_result(self):
        decoded = self.round_trip(
            CompletionMessage("invocation-id", result=42, error=None))

        self.assertIsInstance(decoded, CompletionMessage)
        self.assertEqual(decoded.result, 42)
        self.assertIsNone(decoded.error)

    def test_encode_decode_completion_error(self):
        decoded = self.round_trip(
            CompletionMessage("invocation-id", result=None, error="boom"))

        self.assertIsInstance(decoded, CompletionMessage)
        self.assertEqual(decoded.error, "boom")
        self.assertIsNone(decoded.result)

    def test_encode_decode_stream_invocation(self):
        decoded = self.round_trip(
            StreamInvocationMessage("invocation-id", "Counter", [10, 500]))

        self.assertIsInstance(decoded, StreamInvocationMessage)
        self.assertEqual(decoded.invocation_id, "invocation-id")
        self.assertEqual(decoded.target, "Counter")
        self.assertEqual(decoded.arguments, [10, 500])

    def test_encode_decode_cancel_invocation(self):
        decoded = self.round_trip(CancelInvocationMessage("invocation-id"))

        self.assertIsInstance(decoded, CancelInvocationMessage)
        self.assertEqual(decoded.invocation_id, "invocation-id")

    def test_encode_decode_ping(self):
        decoded = self.round_trip(PingMessage())

        self.assertIsInstance(decoded, PingMessage)

    def test_encode_decode_close(self):
        decoded = self.round_trip(CloseMessage("closed", True))

        self.assertIsInstance(decoded, CloseMessage)
        self.assertEqual(decoded.error, "closed")
        self.assertTrue(decoded.allow_reconnect)

    def test_encode_decode_close_without_error(self):
        decoded = self.round_trip(CloseMessage(None, False))

        self.assertIsInstance(decoded, CloseMessage)
        self.assertIsNone(decoded.error)
        self.assertFalse(decoded.allow_reconnect)

    def test_encode_decode_ack(self):
        decoded = self.round_trip(AckMessage(36))

        self.assertIsInstance(decoded, AckMessage)
        self.assertEqual(decoded.sequence_id, 36)

    def test_encode_decode_sequence(self):
        decoded = self.round_trip(SequenceMessage(19))

        self.assertIsInstance(decoded, SequenceMessage)
        self.assertEqual(decoded.sequence_id, 19)

    def test_encode_unknown_message_type_raises(self):
        self.assertRaises(
            ValueError,
            lambda: self.protocol.encode(UnknownTypeMessage()))

    def test_decode_unknown_result_kind_raises(self):
        self.assertRaises(
            Exception,
            lambda: self.protocol._decode_message(
                [3, {}, "invocation-id", 99]))

    def test_decode_unknown_message_type_raises(self):
        self.assertRaises(
            Exception,
            lambda: self.protocol._decode_message([99]))

    def test_to_varint_boundaries(self):
        self.assertEqual(self.protocol._to_varint(0), b"\x00")
        self.assertEqual(self.protocol._to_varint(127), b"\x7f")
        self.assertEqual(self.protocol._to_varint(128), b"\x80\x01")

    def test_parse_messages_multi_byte_length(self):
        message = InvocationMessage("invocation-id", "Target", ["x" * 200])

        decoded = self.protocol.parse_messages(self.protocol.encode(message))

        self.assertEqual(decoded[0].arguments, ["x" * 200])

    def test_parse_messages_truncated_varint(self):
        # 0x80 has the continuation bit set but there are no more bytes
        self.assertEqual(self.protocol.parse_messages(b"\x80"), [])

    def test_parse_messages_varint_too_long(self):
        # More than 5 continuation bytes is an invalid varint
        self.assertEqual(self.protocol.parse_messages(b"\x80" * 5), [])

    def test_parse_messages_skips_malformed_frame(self):
        malformed = b"\x01\xc1"  # length 1, 0xC1 is never valid msgpack
        good = self.protocol.encode(PingMessage())

        messages = self.protocol.parse_messages(malformed + good)

        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], PingMessage)

    def test_parse_messages_incomplete_frame(self):
        body = msgpack.packb([6])
        # Claim more bytes than are actually present
        raw = self.protocol._to_varint(len(body) + 10) + body

        self.assertEqual(self.protocol.parse_messages(raw), [])

    def test_encode_handshake_request(self):
        encoded = self.protocol.encode(
            HandshakeRequestMessage("messagepack", 1))

        self.assertEqual(
            encoded,
            json.dumps({"protocol": "messagepack", "version": 1})
            + self.protocol.record_separator)

    def test_decode_handshake_invalid_bytes_raises(self):
        self.assertRaises(
            Exception,
            lambda: self.protocol.decode_handshake(b"not json"))

    def test_decode_handshake_string(self):
        response, messages = self.protocol.decode_handshake('{"error": null}')

        self.assertIsNone(response.error)
        self.assertEqual(messages, [])

    def test_decode_handshake_bytes_with_trailing_messages(self):
        handshake = b'{"error": null}' + bytes([0x1E])
        payload = self.protocol.encode(PingMessage())

        response, messages = self.protocol.decode_handshake(
            handshake + payload)

        self.assertIsNone(response.error)
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], PingMessage)


if __name__ == "__main__":
    unittest.main()
