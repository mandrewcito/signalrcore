import json
from ..messages.handshake.request import HandshakeRequestMessage
from ..messages.handshake.response import HandshakeResponseMessage


class BaseHubProtocol(object):
    def __init__(self, protocol, version, transfer_format, record_separator):
        self.protocol = protocol
        self.version = version
        self.transfer_format = transfer_format
        self.record_separator = record_separator

    def decode_handshake(self, raw_message):
        data = json.loads(raw_message.replace(self.record_separator, ""))
        return HandshakeResponseMessage(data["error"] if "error" in data.keys() else None)

    def handshake_message(self):
        return HandshakeRequestMessage(self.protocol, self.version)

    def parse_messages(self, raw_message):
        raise ValueError("Protocol must implement this method")

    def write_message(self, hub_message):
        raise ValueError("Protocol must implement this method")
