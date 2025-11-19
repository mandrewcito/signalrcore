import enum
from ..protocol.json_hub_protocol import JsonHubProtocol
from ..helpers import Helpers


class TransportState(enum.Enum):
    connecting = 0  # connection established, handshake not received
    connected = 1  # connection established, handshake received
    reconnecting = 2  # connection not established, reconnecting
    disconnected = 3  # connection not established


class BaseTransport(object):
    def __init__(self, protocol=JsonHubProtocol(), on_message=None):
        self.protocol = protocol
        self._on_message = on_message
        self.logger = Helpers.get_logger()
        self._on_open = lambda: self.logger.info("on_connect not defined")
        self._on_close = lambda: self.logger.info("on_disconnect not defined")
        self._on_reconnect =\
            lambda: self.logger.info("on_reconnect not defined")

        self.state = TransportState.disconnected

    def _set_state(self, new_state: TransportState):
        """Internal helper to change state and call appropriate callbacks."""
        if new_state == self.state:
            return  # no-op

        old_state = self.state
        self.state = new_state
        self.logger.debug(
            f"Transport state changed: {old_state.name} → {new_state.name}")

        if old_state == TransportState.connecting and\
                new_state == TransportState.connected:
            self._on_open()

        elif new_state == TransportState.disconnected:
            self._on_close()

        elif old_state == TransportState.reconnecting and\
                new_state == TransportState.connected:
            self._on_reconnect()

    def is_connected(self):
        return self.state == TransportState.connected

    def is_connecting(self):
        return self.state == TransportState.connecting

    def is_reconnecting(self):
        return self.state == TransportState.reconnecting

    def is_disconnected(self):
        return self.state == TransportState.disconnected

    def on_open_callback(self, callback):
        self._on_open = callback

    def on_close_callback(self, callback):
        self._on_close = callback

    def on_reconnect_callback(self, callback):
        self._on_reconnect = callback

    def start(self):  # pragma: no cover
        raise NotImplementedError()

    def stop(self):  # pragma: no cover
        raise NotImplementedError()

    def is_running(self):
        return self.state != TransportState.disconnected

    def send(self, message, on_invocation=None):  # pragma: no cover
        raise NotImplementedError()
