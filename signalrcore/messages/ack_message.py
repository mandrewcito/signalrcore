"""
### Ack Message Encoding
An `Ack` message is a JSON object with the following properties

* `type` - A `Number` with the literal value `8`, indicating that
    this message is an `Ack`.
* `sequenceId` - A `Number` specifying how many trackable messages
    have been received.

Example:
```json
{
    "type": 8,
    "sequenceId": 1394
}
```
"""
from .base_message import BaseHeadersMessage, MessageType


class AckMessage(BaseHeadersMessage):
    def __init__(self, sequence_id: int, **kwargs):
        super().__init__(MessageType.ack.value, **kwargs)
        self.sequence_id = sequence_id
