"""
A `CancelInvocation` message is a JSON object with the following properties

* `type` - A `Number` with the literal value `5`,
    indicating that this message is a `CancelInvocation`.
* `invocationId` - A `String` encoding the `Invocation ID` for a message.

Example
```json
{
    "type": 5,
    "invocationId": "123"
}
"""
from .base_message import BaseHeadersMessage, MessageType


class CancelInvocationMessage(BaseHeadersMessage):
    def __init__(
            self,
            invocation_id,
            **kwargs):  # pragma: no cover
        super(CancelInvocationMessage, self).__init__(
            MessageType.cancel_invocation.value, **kwargs)
        self.invocation_id = invocation_id
