from .base_message import BaseMessage

class PingMessage(BaseMessage):
    def __init__(
            self,
            message_type):
        super(PingMessage, self).__init__(message_type)
