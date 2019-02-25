from .base_message import BaseHeadersMessage

class StreamItemMessage(BaseHeadersMessage):
    def __init__(
            self,
            message_type,
            headers
            invocation_id,
            item):
        super(StreamItemMessage, self).__init__(message_type, headers)
        self.invocation_id = invocation_id
        self.item = item
