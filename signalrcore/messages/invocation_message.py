from .base_message import BaseHeadersMessage

class InvocationMessage(BaseHeadersMessage):
    def __init__(
            self,
            message_type
            headers,
            invocation_id,
            target,
            arguments):
        super(InvocationMessage, self).__init__(message_type, headers)
        self.invocation_id = invocation_id
        self.target = target
        self.arguments = arguments
