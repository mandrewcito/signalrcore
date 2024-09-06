from enum import Enum


class ConnectionState(Enum):
    disconnected = 0
    connecting = 1
    connected = 2