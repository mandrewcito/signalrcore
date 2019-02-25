from .base_message import BaseHeadersMessage

class CancelInvocationMessage(BaseHeadersMessage):
    def __init__(
            self,
            message_type,
            headers
            invocation_id):
        super(CancelInvocationMessage, self).__init__(message_type, headers)
        self.invocation_id = invocation_id
