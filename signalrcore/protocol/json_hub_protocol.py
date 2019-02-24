import json
from .base_hub_protocol import BaseHubProtocol
from ..messages.message import Message
from ..messages.message_type import MessageType
from json import JSONEncoder  # TODO , JSONDecoder


class MyEncoder(JSONEncoder):
    def default(self, o):
        if type(o) is MessageType:
            return o.value
        return o.__dict__


class JsonHubProtocol(BaseHubProtocol):
    def __init__(self):
        super(JsonHubProtocol, self).__init__("json", 1, "Text", chr(0x1E))
        self.encoder = MyEncoder()

    def parse_messages(self, raw):
        raw_messages = [record.replace(self.record_separator, "") for record in raw.split(self.record_separator)
                        if record is not None and record is not "" and record is not self.record_separator]
        result = []
        for raw_message in raw_messages:
            dict_message = json.loads(raw_message)
            result.append(Message(
                dict_message["type"],
                dict_message["invocation_id"] if "invocation_id" in dict_message.keys() else None,
                dict_message["target"],
                dict_message["arguments"]))
        return result

    def encode(self, message):
        return self.encoder.encode(message) + self.record_separator
