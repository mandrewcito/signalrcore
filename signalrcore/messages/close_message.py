"""
A `Close` message is a JSON object with the following properties

* `type` - A `Number` with the literal value `7`,
    indicating that this message is a `Close`.
* `error` - An optional `String` encoding the error message.

Example - A `Close` message without an error
```json
{
    "type": 7
}
```

Example - A `Close` message with an error
```json
{
    "type": 7,
    "error": "Connection closed because of an error!",
    "allowReconnect":true
}
```
"""
from .base_message import BaseHeadersMessage, MessageType


class CloseMessage(BaseHeadersMessage):
    def __init__(
            self,
            error,
            allow_reconnect,
            **kwargs):
        super(CloseMessage, self).__init__(MessageType.close.value, **kwargs)
        self.error = error
        self.allow_reconnect = allow_reconnect
