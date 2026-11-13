import json
import msgpack
from .base_hub_protocol import BaseHubProtocol
from ..messages.handshake.request import HandshakeRequestMessage
from ..messages.handshake.response import HandshakeResponseMessage
from ..messages.invocation_message\
    import InvocationMessage, InvocationClientStreamMessage  # 1
from ..messages.stream_item_message import StreamItemMessage  # 2
from ..messages.completion_message import CompletionMessage  # 3
from ..messages.stream_invocation_message import StreamInvocationMessage  # 4
from ..messages.cancel_invocation_message import CancelInvocationMessage  # 5
from ..messages.ping_message import PingMessage  # 6
from ..messages.close_message import CloseMessage  # 7
from ..messages.ack_message import AckMessage  # 8
from ..messages.sequence_message import SequenceMessage  # 9

from ..helpers import Helpers
from ..types import HubProtocolEncoding, RECORD_SEPARATOR, DEFAULT_ENCODING


class MessagePackHubProtocol(BaseHubProtocol):

    def __init__(self, version: int = 1):
        super(MessagePackHubProtocol, self).__init__(
            "messagepack",
            version,
            HubProtocolEncoding.binary,
            RECORD_SEPARATOR)
        self.logger = Helpers.get_logger()

    def _read_varint(self, raw, offset):
        length = 0
        num_bytes = 0
        num_bits_to_shift = [0, 7, 14, 21, 28]

        while True:
            if offset + num_bytes >= len(raw):
                raise ValueError("Cannot read message length")

            byte_read = raw[offset + num_bytes]
            length |= (byte_read & 0x7F) << num_bits_to_shift[num_bytes]
            num_bytes += 1

            if byte_read & 0x80 == 0:
                return length, num_bytes

            if num_bytes >= len(num_bits_to_shift):
                raise ValueError("Cannot read message length")

    def parse_messages(self, raw):
        messages = []
        offset = 0

        while offset < len(raw):
            try:
                length, num_bytes = self._read_varint(raw, offset)
            except Exception as ex:
                self.logger.error("Parse messages Error {0}".format(ex))
                self.logger.error("raw msg '{0}'".format(raw))
                break

            offset += num_bytes

            # Incomplete frame, wait for the remaining bytes
            if offset + length > len(raw):
                self.logger.debug(
                    "Incomplete message received, waiting for more data")
                break

            try:
                values = msgpack.unpackb(raw[offset: offset + length])
                messages.append(self._decode_message(values))
            except Exception as ex:
                # A single malformed message must not discard the
                # messages that follow it.
                self.logger.error("Parse message Error {0}".format(ex))
                self.logger.error(
                    "raw msg '{0}'".format(raw[offset: offset + length]))

            offset += length

        return messages

    def decode_handshake(self, raw_message):
        try:
            has_various_messages = 0x1E in raw_message
            handshake_data = raw_message[0: raw_message.index(0x1E)]\
                if has_various_messages else raw_message
            messages = self.parse_messages(
                raw_message[raw_message.index(0x1E) + 1:])\
                if has_various_messages else []
            data = json.loads(
                handshake_data.decode(DEFAULT_ENCODING)
                if type(handshake_data) is bytes else
                handshake_data)
            return HandshakeResponseMessage(data.get("error", None)), messages
        except Exception as ex:
            if type(raw_message) is str:
                data = json.loads(raw_message[0: raw_message.index("}") + 1])
                return HandshakeResponseMessage(data.get("error", None)), []
            self.logger.error(raw_message)
            self.logger.error(ex)
            raise ex

    def encode(self, message):
        if type(message) is HandshakeRequestMessage:
            content = json.dumps(message.__dict__)
            return content + self.record_separator

        msg = self._encode_message(message)
        encoded_message = msgpack.packb(msg)
        varint_length = self._to_varint(len(encoded_message))
        return varint_length + encoded_message

    def _encode_message(self, message):
        message_type = message.type.value

        if message_type == 1:  # Invocation
            return [
                1,
                message.headers,
                message.invocation_id,
                message.target,
                message.arguments,
                getattr(message, "stream_ids", []) or []
            ]

        if message_type == 2:  # StreamItem
            return [2, message.headers, message.invocation_id, message.item]

        if message_type == 3:  # Completion
            # ResultKind: 1 = error, 2 = void, 3 = non-void
            error = getattr(message, "error", None)
            result = getattr(message, "result", None)

            if error is not None:
                return [3, message.headers, message.invocation_id, 1, error]
            if result is not None:
                return [3, message.headers, message.invocation_id, 3, result]
            return [3, message.headers, message.invocation_id, 2]

        if message_type == 4:  # StreamInvocation
            return [
                4,
                message.headers,
                message.invocation_id,
                message.target,
                message.arguments,
                message.stream_ids or []
            ]

        if message_type == 5:  # CancelInvocation
            return [5, message.headers, message.invocation_id]

        if message_type == 6:  # Ping
            return [6]

        if message_type == 7:  # Close
            return [7, message.error, bool(message.allow_reconnect)]

        if message_type == 8:  # Ack
            return [8, message.sequence_id]

        if message_type == 9:  # Sequence
            return [9, message.sequence_id]

        raise ValueError(
            "Cannot encode unknown message type {0}".format(message_type))

    def _decode_message(self, raw):
        # {} {"error"}
        # [1, Headers, InvocationId, Target, [Arguments], [StreamIds]]
        # [2, Headers, InvocationId, Item]
        # [3, Headers, InvocationId, ResultKind, Result]
        # [4, Headers, InvocationId, Target, [Arguments], [StreamIds]]
        # [5, Headers, InvocationId]
        # [6]
        # [7, Error, AllowReconnect?]
        # [8, SequenceId]
        # [9, SequenceId]

        if raw[0] == 1:  # InvocationMessage
            stream_ids = raw[5] if len(raw) > 5 else []
            if stream_ids:
                return InvocationClientStreamMessage(
                    headers=raw[1],
                    invocation_id=raw[2],
                    stream_ids=stream_ids,
                    target=raw[3],
                    arguments=raw[4])
            else:
                return InvocationMessage(
                    headers=raw[1],
                    invocation_id=raw[2],
                    target=raw[3],
                    arguments=raw[4])

        elif raw[0] == 2:  # StreamItemMessage
            return StreamItemMessage(
                headers=raw[1],
                invocation_id=raw[2],
                item=raw[3])

        elif raw[0] == 3:  # CompletionMessage
            result_kind = raw[3]
            if result_kind == 1:
                return CompletionMessage(
                    headers=raw[1],
                    invocation_id=raw[2],
                    result=None,
                    error=raw[4])

            elif result_kind == 2:
                return CompletionMessage(
                    headers=raw[1], invocation_id=raw[2],
                    result=None, error=None)

            elif result_kind == 3:
                return CompletionMessage(
                    headers=raw[1], invocation_id=raw[2],
                    result=raw[4], error=None)
            else:
                raise Exception("Unknown result kind.")

        elif raw[0] == 4:  # StreamInvocationMessage
            return StreamInvocationMessage(
                headers=raw[1],
                invocation_id=raw[2],
                target=raw[3],
                arguments=raw[4],
                stream_ids=raw[5] if len(raw) > 5 else [])

        elif raw[0] == 5:  # CancelInvocationMessage
            return CancelInvocationMessage(
                headers=raw[1],
                invocation_id=raw[2])

        elif raw[0] == 6:  # PingMessageEncoding
            return PingMessage()

        elif raw[0] == 7:  # CloseMessageEncoding
            return CloseMessage(
                error=raw[1] if len(raw) > 1 else None,
                allow_reconnect=raw[2] if len(raw) > 2 else None)
        elif raw[0] == 8:  # pragma: no cover # AckMessage
            return AckMessage(sequence_id=raw[1])
        elif raw[0] == 9:  # pragma: no cover # SequenceMessage
            return SequenceMessage(sequence_id=raw[1])

        raise Exception("Unknown message type.")  # pragma: no cover

    def _to_varint(self, value):
        buffer = b''

        while True:

            byte = value & 0x7f
            value >>= 7

            if value:
                buffer += bytes((byte | 0x80, ))
            else:
                buffer += bytes((byte, ))
                break

        return buffer
