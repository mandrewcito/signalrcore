import json

from ..messages.handshake.request import HandshakeRequestMessage
from ..messages.handshake.response import HandshakeResponseMessage
from ..messages.invocation_message import InvocationMessage  # 1
from ..messages.stream_item_message import StreamItemMessage  # 2
from ..messages.completion_message import CompletionMessage  # 3
from ..messages.stream_invocation_message import StreamInvocationMessage  # 4
from ..messages.cancel_invocation_message import CancelInvocationMessage  # 5
from ..messages.ping_message import PingMessage  # 6
from ..messages.close_message import CloseMessage  # 7
from ..messages.message_type import MessageType


class BaseHubProtocol(object):
    def __init__(self, protocol, version, transfer_format, record_separator):
        self.protocol = protocol
        self.version = version
        self.transfer_format = transfer_format
        self.record_separator = record_separator

    @staticmethod
    def get_message(dict_message):
        message_type = MessageType(dict_message["type"])
        if message_type is MessageType.invocation:
            return InvocationMessage(
                dict_message["headers"]
                if "headers" in dict_message.keys() else {},
                dict_message["invocationId"]
                if "invocationId" in dict_message.keys() else None,
                dict_message["target"],
                dict_message["arguments"])
        if message_type is MessageType.stream_item:
            return StreamItemMessage(
                dict_message["headers"]
                if "headers" in dict_message.keys() else {},
                dict_message["invocationId"]
                if "invocationId" in dict_message.keys() else None,
                dict_message["item"]
                )
        if message_type is MessageType.completion:
            return CompletionMessage(
                dict_message["headers"]
                if "headers" in dict_message.keys() else {},
                dict_message["invocationId"],
                dict_message["result"]
                if "result" in dict_message.keys() else None,
                dict_message["error"]
                if "error" in dict_message.keys() else None
                )
        if message_type is MessageType.stream_invocation:
            return StreamInvocationMessage(
                dict_message["headers"]
                if "headers" in dict_message.keys() else {},
                dict_message["invocationId"],
                dict_message["target"],
                dict_message["arguments"])
        if message_type is MessageType.cancel_invocation:
            return CancelInvocationMessage(
                dict_message["headers"]
                if "headers" in dict_message.keys() else {},
                dict_message["invocationId"])
        if message_type is MessageType.ping:
            return PingMessage()
        if message_type is MessageType.close:
            return CloseMessage(
                dict_message["headers"]
                if "headers" in dict_message.keys() else {},
                dict_message["error"]
                if "error" in dict_message.keys() else None
                )

    def decode_handshake(self, raw_message):
        messages = raw_message.split(self.record_separator)
        data = json.loads(messages[0])
        return HandshakeResponseMessage(
            data["error"] if "error" in data.keys() else None)

    def handshake_message(self):
        return HandshakeRequestMessage(self.protocol, self.version)

    def parse_messages(self, raw_message):
        raise ValueError("Protocol must implement this method")

    def write_message(self, hub_message):
        raise ValueError("Protocol must implement this method")
