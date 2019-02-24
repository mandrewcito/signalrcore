from .message_type import MessageType


class Message(object):
    def __init__(self, message_type, invocation_id, target, arguments):
        self.type = MessageType(message_type)
        self.invocation_id = invocation_id
        self.target = target
        self.arguments = arguments
