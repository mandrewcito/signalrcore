import json

from json import JSONEncoder
from typing import Tuple, Any

from .base_hub_protocol import BaseHubProtocol
from ..messages.message_type import MessageType
from ..messages.handshake.response import HandshakeResponseMessage
from ..messages.ping_message import PingMessage
from ..helpers import Helpers
from ..types import HubProtocolEncoding, RECORD_SEPARATOR


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
    def __init__(self, version: int = 1):
        super(JsonHubProtocol, self).__init__(
            "json",
            version,
            HubProtocolEncoding.text,
            RECORD_SEPARATOR)
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
    def __init__(self, version: int = 1):
        super(JsonHubSseProtocol, self).__init__(
            "json", version, HubProtocolEncoding.text, RECORD_SEPARATOR)
        self.encoder = MyEncoder()
        self.logger = Helpers.get_logger()

    def decode_handshake(
            self,
            raw: str) -> Tuple[HandshakeResponseMessage, Any]:

        raw_messages = self._split_messages(raw)
        data = json.loads(raw_messages[0])

        return\
            HandshakeResponseMessage(data.get("error", None)), \
            self._parse_messages(raw_messages[1:])

    def _split_messages(self, raw) -> list:
        return [
            record.replace(self.record_separator, "")
            for record in raw.split(self.record_separator)
            if record is not None
            and record != ""
            and record != self.record_separator
            and record != "\r"
        ]

    def _parse_messages(self, raw_messages):
        result = []

        for raw_message in raw_messages:

            if not raw_message.startswith("{"):
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

    def parse_messages(self, raw):
        Helpers.get_logger().debug("Raw message incoming: ")
        Helpers.get_logger().debug(raw)

        raw_messages = self._split_messages(raw)

        return self._parse_messages(raw_messages)

    def encode(self, message):
        Helpers.get_logger()\
            .debug(self.encoder.encode(message))
        return self.encoder.encode(message).encode("utf-8")
