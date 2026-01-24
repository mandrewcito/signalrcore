import json

from json import JSONEncoder
from typing import Tuple, Any

from .base_hub_protocol import BaseHubProtocol
from ..messages.message_type import MessageType
from ..messages.handshake.response import HandshakeResponseMessage
from ..messages.ping_message import PingMessage
from ..helpers import Helpers


class MyEncoder(JSONEncoder):
    # https://github.com/PyCQA/pylint/issues/414
    def default(self, o):
        if type(o) is MessageType:
            return o.value
        data = o.__dict__
        if "invocation_id" in data:
            data["invocationId"] = data["invocation_id"]
            del data["invocation_id"]
        if "stream_ids" in data:
            data["streamIds"] = data["stream_ids"]
            del data["stream_ids"]
        return data


class JsonHubProtocol(BaseHubProtocol):
    def __init__(self):
        super(JsonHubProtocol, self).__init__("json", 1, "Text", chr(0x1E))
        self.encoder = MyEncoder()

    def parse_messages(self, raw):
        Helpers.get_logger().debug("Raw message incoming: ")
        Helpers.get_logger().debug(raw)
        raw_messages = [
            record.replace(self.record_separator, "")
            for record in raw.split(self.record_separator)
            if record is not None and record != ""
            and record != self.record_separator
            ]
        result = []
        for raw_message in raw_messages:
            dict_message = json.loads(raw_message)
            if len(dict_message.keys()) > 0:
                result.append(self.get_message(dict_message))
        return result

    def encode(self, message):
        Helpers.get_logger()\
            .debug(self.encoder.encode(message) + self.record_separator)
        return self.encoder.encode(message) + self.record_separator


class JsonHubSseProtocol(BaseHubProtocol):
    # records appear wrapped with b'\n[content]\r\n' so we unwrap
    def __init__(self):
        super(JsonHubSseProtocol, self).__init__(
            "json", 1, "Text", chr(0x1E))
        self.socket_record_separator = chr(0x1E)
        self.encoder = MyEncoder()
        self.logger = Helpers.get_logger()
        self.handshake_str = "data: "

    def decode_handshake(
            self,
            raw_message: str) -> Tuple[HandshakeResponseMessage, Any]:

        raw_messages = [
            record.replace(self.record_separator, "")
            for record in raw_message.split(self.record_separator)
            if record is not None and record != ""
            and record != self.record_separator
            ]

        error = None\
            if raw_messages[0] == self.handshake_str\
            else raw_messages[0]

        return HandshakeResponseMessage(error), []

    def parse_messages(self, raw):
        Helpers.get_logger().debug("Raw message incoming: ")
        Helpers.get_logger().debug(raw)

        raw_messages = [
            record.replace(self.record_separator, "")
            for record in raw.split(self.record_separator)
            if record is not None and record != ""
            and record != self.record_separator
            ]

        result = []

        for raw_message in raw_messages:
            if raw_message == self.handshake_str:
                continue
            try:
                dict_message = json.loads(raw_message)
            except Exception as ex:
                self.logger.error(ex)
                self.logger.error(raw_message)
                continue

            if len(dict_message.keys()) > 0:
                result.append(self.get_message(dict_message))
            else:
                result.append(PingMessage())

        return result

    def encode(self, message):
        Helpers.get_logger()\
            .debug(self.encoder.encode(message))
        return self.encoder.encode(message).encode("utf-8")
