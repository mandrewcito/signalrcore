import json
from .base_hub_protocol import BaseHubProtocol

from ..messages.message_type import MessageType
from json import JSONEncoder
"""
Invocation
{
    "type": 1,
    "headers": {
        "Foo": "Bar"
    },
    "invocationId": "123",
    "target": "Send",
    "arguments": [
        42,
        "Test Message"
    ]
}
{
    "type": 1,
    "target": "Send",
    "arguments": [
        42,
        "Test Message"
    ]
}
{
    "type": 1,
    "invocationId": "123",
    "target": "Send",
    "arguments": [
        42,
        "Test Message"
    ]
}
StreamItem
{
    "type": 2,
    "invocationId": "123",
    "item": 42
}
Completion
{
    "type": 3,
    "invocationId": "123"
}
{
    "type": 3,
    "invocationId": "123",
    "result": 42
}
{
    "type": 3,
    "invocationId": "123",
    "error": "It didn't work!"
}
StreamInvocation
{
    "type": 4,
    "invocationId": "123",
    "target": "Send",
    "arguments": [
        42,
        "Test Message"
    ]
}
CancelInvocation
{
    "type": 5,
    "invocationId": "123"
}
Ping
{
    "type": 6
}
Close
{
    "type": 7
}
{
    "type": 7,
    "error": "Connection closed because of an error!"
}
"""


class MyEncoder(JSONEncoder):
    # https://github.com/PyCQA/pylint/issues/414
    def default(self, o):
        if type(o) is MessageType:
            return o.value
        data = o.__dict__
        if "invocation_id" in data:
            data["invocationId"] = data["invocation_id"]
            del data["invocation_id"]
        return data


class JsonHubProtocol(BaseHubProtocol):
    def __init__(self):
        super(JsonHubProtocol, self).__init__("json", 1, "Text", chr(0x1E))
        self.encoder = MyEncoder()

    def parse_messages(self, raw):
        raw_messages = [
            record.replace(self.record_separator, "")
            for record in raw.split(self.record_separator)
            if record is not None and record is not "" and record is not self.record_separator
            ]
        result = []
        for raw_message in raw_messages:
            dict_message = json.loads(raw_message)
            result.append(self.get_message(dict_message))
        return result

    def encode(self, message):
        return self.encoder.encode(message) + self.record_separator
