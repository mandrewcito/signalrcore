from .base_message import BaseHeadersMessage

class StreamInvocationMessage(BaseHeadersMessage):
    def __init__(
            self,
            message_type,
            headers
            invocation_id,
            target,
            arguments):
        super(StreamInvocationMessage, self).__init__(message_type, headers)
        self.invocation_id = invocation_id
        self.target = target
        self.arguments = arguments
