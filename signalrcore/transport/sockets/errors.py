from typing import Optional


class NoHeaderException(Exception):
    """Error reading messages from socket, empty content
    """
    pass


class SocketHandshakeError(Exception):
    """Error during connection

    Args:
        msg (str): message
    """
    def __init__(self, msg: str):  # pragma: no cover
        super().__init__(msg)


class SocketClosedError(Exception):
    """Socket closed by the server fin opcode: 129, masked len 3

    Args:
        data (bytes): raw bytes sent by the server
    """
    def __init__(self, data: Optional[bytes] = None):  # pragma: no cover
        self.data = data
        super().__init__("Socket closed by the the server")
