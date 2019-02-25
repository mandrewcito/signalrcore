from .base_message import BaseHeadersMessage

class CompletionMessage(BaseHeadersMessage):
    def __init__(
            self,
            message_type,
            headers,
            invocation_id,
            result,
            error):
        super(CompletionMessage, self).__init__(message_type, headers)
        self.invocation_id = invocation_id
        self.result = result
        self.error = error
