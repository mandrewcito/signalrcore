import sys
if sys.version_info.major is 2:
    from aenum import Enum
else:
    from enum import Enum


class ConnectionState(Enum):
    connecting = 0
    connected = 1
    reconnecting = 2
    disconnected = 4
