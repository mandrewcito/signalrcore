from .base_message import BaseHeadersMessage

class PingMessage(BaseHeadersMessage):
    def __init__(
            self,
            message_type,
            headers,
            error):
        super(PingMessage, self).__init__(message_type, headers)
        self.error = error
