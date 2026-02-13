"""
### Sequence Message Encoding
A `Sequence` message is a JSON object with the following
    properties

* `type` - A `Number` with the literal value `9`, indicating that
    this message is a `Sequence`.
* `sequenceId` - A `Number` specifying what the new starting message
    number will be. Only sent on reconnects.

Example:
```json
{
    "type": 9,
    "sequenceId": 1234
}
```
"""
from .base_message import BaseHeadersMessage, MessageType


class SequenceMessage(BaseHeadersMessage):
    def __init__(self, sequence_id: int, **kwargs):  # pragma: no cover
        super().__init__(MessageType.sequence.value, **kwargs)
        self.sequence_id = sequence_id
