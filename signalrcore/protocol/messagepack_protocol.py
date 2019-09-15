from .base_hub_protocol import BaseHubProtocol
from ..messages.message_type import MessageType
from json import JSONEncoder  # TODO , JSONDecoder

# [1, Headers, InvocationId, NonBlocking, Target, [Arguments]]
# [2, Headers, InvocationId, Item]
# [3, Headers, InvocationId, ResultKind, Result?]
# [4, Headers, InvocationId, Target, [Arguments]]
# [5, Headers, InvocationId]
# [6]
# [7, Error]


class MyEncoder(JSONEncoder):
    #  https://github.com/PyCQA/pylint/issues/414
    def default(self, o):
        if type(o) is MessageType:
            return o.value
        return o.__dict__


class MessagepackProtocol(BaseHubProtocol):
    def __init__(self):
        super(MessagepackProtocol, self).__init__(
            "messagepack", 1, "Text", chr(0x1E))

    def parse_messages(self, raw):
        raise ValueError(" NOt implemented yet")

    def encode(self, message):
        raise ValueError(" NOt implemented yet")
