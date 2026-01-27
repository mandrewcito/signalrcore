import enum
from typing import Callable, Dict, Optional
from ..protocol.json_hub_protocol import JsonHubProtocol
from ..helpers import Helpers
from ..transport.base_reconnection import BaseReconnection
from ..hub.negotiation import NegotiateResponse, NegotiationHandler


class TransportState(enum.Enum):
    connecting = 0  # connection established, handshake not received
    connected = 1  # connection established, handshake received
    reconnecting = 2  # connection not established, reconnecting
    disconnected = 3  # connection not established


class BaseTransport(object):
    def __init__(
            self,
            url: str = None,
            connection_id: str = None,
            is_binary: bool = False,
            token: Optional[str] = None,
            headers: Optional[Dict] = None,
            proxies: Optional[Dict] = None,
            verify_ssl: bool = True,
            enable_trace: bool = False,
            on_open: Callable = None,
            on_close: Callable = None,
            on_reconnect: Callable = None,
            protocol=JsonHubProtocol(),
            reconnection_handler: BaseReconnection = None,
            on_message: Callable = None):
        self.url = url
        self.is_binary = is_binary
        self.headers = headers
        self.token = token
        self.verify_ssl = verify_ssl
        self.enable_trace = enable_trace
        self.verify_ssl = verify_ssl
        self.connection_id = connection_id
        self.proxies = proxies
        self.protocol = protocol
        self._on_message = on_message
        self.reconnection_handler = reconnection_handler
        self.logger = Helpers.get_logger()
        self._on_open = on_open
        self._on_close = on_close
        self._on_reconnect = on_reconnect

        self.state = TransportState.disconnected
        self.reconnection_handler = reconnection_handler

    def _set_state(self, new_state: TransportState):
        """Internal helper to change state and call appropriate callbacks."""
        if new_state == self.state:
            return  # no-op

        old_state = self.state
        self.state = new_state

        self.logger.debug(
            f"Transport state changed: {old_state.name} → {new_state.name}")

        was_connecting = old_state == TransportState.connecting
        was_connected = old_state == TransportState.connected
        was_reconnecting = old_state == TransportState.reconnecting

        if was_connecting and self.is_connected():
            self._on_open()
        elif (was_connected or was_reconnecting)\
                and self.is_disconnected():
            self._on_close()
        elif was_reconnecting and self.is_connected():
            self._on_reconnect()

    def is_connected(self):
        return self.state == TransportState.connected

    def is_connecting(self):  # pragma: no cover
        return self.state == TransportState.connecting

    def is_reconnecting(self):
        return self.state == TransportState.reconnecting

    def is_disconnected(self):
        return self.state == TransportState.disconnected

    def start(self):  # pragma: no cover
        raise NotImplementedError()

    def stop(self):  # pragma: no cover
        raise NotImplementedError()

    def is_running(self):
        return self.state != TransportState.disconnected

    def send(self, message, on_invocation=None):  # pragma: no cover
        raise NotImplementedError()

    def negotiate(self) -> NegotiateResponse:
        handler = NegotiationHandler(
            self.url,
            self.headers,
            self.proxies,
            self.verify_ssl
        )

        self.url, self.headers, response = handler.negotiate()
        self.connection_id = response.connection_id

        return response
