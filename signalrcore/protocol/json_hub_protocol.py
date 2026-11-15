import json

from json import JSONEncoder

from .base_hub_protocol import BaseHubProtocol
from ..messages.message_type import MessageType
from ..types import HubProtocolEncoding, RECORD_SEPARATOR


class MyEncoder(JSONEncoder):
    # Python attribute name -> SignalR protocol field name.
    # https://github.com/PyCQA/pylint/issues/414
    field_names = {
        "invocation_id": "invocationId",
        "stream_ids": "streamIds",
        "sequence_id": "sequenceId",
        "allow_reconnect": "allowReconnect",
    }

    def default(self, o):
        if type(o) is MessageType:
            return o.value
        data = dict(o.__dict__)
        for attribute, field in MyEncoder.field_names.items():
            if attribute in data:
                data[field] = data.pop(attribute)
        # An invocation id of None means the message is not an
        # invocation (client to server streaming), so it must be omitted.
        if data.get("invocationId") is None:
            data.pop("invocationId", None)
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
        self.logger.debug("Raw message incoming: ")
        self.logger.debug(raw)

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
        self.logger\
            .debug(self.encoder.encode(message) + self.record_separator)
        return self.encoder.encode(message) + self.record_separator
