import json
import unittest

from signalrcore.messages.ack_message import AckMessage
from signalrcore.messages.close_message import CloseMessage
from signalrcore.messages.invocation_message import (
    InvocationClientStreamMessage,
    InvocationMessage,
)
from signalrcore.messages.sequence_message import SequenceMessage
from signalrcore.protocol.json_hub_protocol import JsonHubProtocol


class TestJsonHubProtocol(unittest.TestCase):
    def setUp(self):
        self.protocol = JsonHubProtocol()

    def encode_to_dict(self, message):
        encoded = self.protocol.encode(message)
        return json.loads(encoded.rstrip(self.protocol.record_separator))

    def test_client_stream_invocation_omits_null_invocation_id(self):
        message = InvocationClientStreamMessage(
            ["stream-id"],
            "UploadStream",
            [])

        encoded = self.encode_to_dict(message)

        self.assertNotIn("invocationId", encoded)
        self.assertEqual(encoded["streamIds"], ["stream-id"])
        self.assertEqual(encoded["target"], "UploadStream")

    def test_invocation_keeps_invocation_id(self):
        message = InvocationMessage("invocation-id", "SendMessage", [])

        encoded = self.encode_to_dict(message)

        self.assertEqual(encoded["invocationId"], "invocation-id")

    def test_encode_does_not_mutate_message(self):
        message = InvocationClientStreamMessage(
            ["stream-id"],
            "UploadStream",
            [])

        first_encoded = self.protocol.encode(message)
        second_encoded = self.protocol.encode(message)

        self.assertEqual(first_encoded, second_encoded)
        self.assertIsNone(message.invocation_id)
        self.assertEqual(message.stream_ids, ["stream-id"])
        self.assertFalse(hasattr(message, "invocationId"))
        self.assertFalse(hasattr(message, "streamIds"))

    def test_ack_uses_sequence_id_field(self):
        encoded = self.encode_to_dict(AckMessage(7))

        self.assertEqual(encoded["sequenceId"], 7)
        self.assertNotIn("sequence_id", encoded)

    def test_sequence_uses_sequence_id_field(self):
        encoded = self.encode_to_dict(SequenceMessage(9))

        self.assertEqual(encoded["sequenceId"], 9)
        self.assertNotIn("sequence_id", encoded)

    def test_close_uses_allow_reconnect_field(self):
        encoded = self.encode_to_dict(CloseMessage("boom", True))

        self.assertEqual(encoded["allowReconnect"], True)
        self.assertNotIn("allow_reconnect", encoded)
