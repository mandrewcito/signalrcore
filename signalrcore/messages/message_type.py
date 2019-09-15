import sys
if sys.version_info.major is 2:
    from aenum import Enum
else:
    from enum import Enum


class MessageType(Enum):
    invocation = 1
    stream_item = 2
    completion = 3
    stream_invocation = 4
    cancel_invocation = 5
    ping = 6
    close = 7
    invocation_binding_failure = -1
