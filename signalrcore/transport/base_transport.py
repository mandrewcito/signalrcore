import enum
import traceback
import time
from typing import Callable, Dict, Optional
from ..helpers import Helpers
from ..transport.base_reconnection import BaseReconnection
from ..protocol.base_hub_protocol import BaseHubProtocol
from ..hub.negotiation import NegotiateResponse, NegotiationHandler
from .base_client import BaseClient
from ..messages.ping_message import PingMessage
from .reconnection import ConnectionStateChecker


class TransportState(enum.Enum):
    connecting = 0  # connection established, handshake not received
    connected = 1  # connection established, handshake received
    reconnecting = 2  # connection not established, reconnecting
    disconnected = 3  # connection not established


class BaseTransport(object):
    _client: Optional[BaseClient]
    connection_checker: ConnectionStateChecker
    manually_closing: bool

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
            protocol: BaseHubProtocol = None,
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

        self.logger = Helpers.get_logger()

        self._on_message = on_message
        self._on_open = on_open
        self._on_close = on_close
        self._on_reconnect = on_reconnect

        self.state = TransportState.disconnected
        self.reconnection_handler = reconnection_handler
        self.manually_closing = False

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
        try:
            if was_connecting and self.is_connected():
                self._on_open()
            elif (was_connected or was_reconnecting)\
                    and self.is_disconnected():
                self._on_close()
            elif was_reconnecting and self.is_connected():
                self._on_reconnect()
        except Exception as ex:
            raise ex

    def is_connected(self):
        return self.state == TransportState.connected

    def is_connecting(self):  # pragma: no cover
        return self.state == TransportState.connecting

    def is_reconnecting(self):
        return self.state == TransportState.reconnecting

    def is_disconnected(self):
        return self.state == TransportState.disconnected

    def is_trace_enabled(self) -> bool:
        return self._client.is_trace_enabled()

    def is_running(self):
        return self.state != TransportState.disconnected

    def send(self, message, on_invocation=None):  # pragma: no cover
        raise NotImplementedError()

    def negotiate(self) -> NegotiateResponse:
        """Negotiates connection with the signalR server, updates:
            - url
            - headers
            - connection_id

        Returns:
            NegotiateResponse: server negotiate response
        """
        handler = NegotiationHandler(
            self.url,
            self.headers,
            self.proxies,
            self.verify_ssl
        )

        self.url, self.headers, response = handler.negotiate()
        self.connection_id = response.get_id()

        return response

    def create_client(self) -> BaseClient:  # pragma: no cover
        raise NotImplementedError()

    def start(self, reconnection: bool = False):
        if reconnection:
            self.negotiate()
            self._set_state(TransportState.reconnecting)
        else:
            self._set_state(TransportState.connecting)

        self.logger.debug("start url:" + self.url)

        self._client = self.create_client()

        self._client.connect()

        return True

    def dispose(self):
        if not self.is_disconnected():
            self.connection_checker.stop()
            self._client.close()

    def stop(self):
        if self.manually_closing or self.is_disconnected():
            return
        self.manually_closing = True
        self.handshake_received = False
        self.dispose()

    def on_socket_error(self, error: Exception):  # pragma: no cover
        """
        Args:
            error (Exception): websocket error

        Raises:
            HubError: [description]
        """
        self.logger.error(traceback.format_exc(10, True))
        self.logger.error("{0} {1}".format(self, error))
        self.logger.error("{0} {1}".format(error, type(error)))
        self._set_state(TransportState.disconnected)

    def deferred_reconnect(self, sleep_time):
        time.sleep(sleep_time)
        try:
            if not self.connection_alive:
                if not self.connection_checker.running:
                    self.send(PingMessage())
        except Exception as ex:
            self.logger.error(ex)
            self.reconnection_handler.reconnecting = False
            self.connection_alive = False

    def handle_reconnect(self) -> bool:
        if self.is_reconnecting() or self.manually_closing:
            return False

        if self.reconnection_handler is None:
            return False

        if not self._client.is_connection_closed():
            return False

        try:
            self.reconnection_handler.reconnecting = True

            self._set_state(TransportState.reconnecting)

            self._client.dispose()
            self.start(reconnection=True)
        except Exception as ex:
            self.logger.error(ex)
            sleep_time = self.reconnection_handler.next()
            self.deferred_reconnect(sleep_time)
        return True

    def send_handshake(self):
        msg = self.protocol.handshake_message()
        self.handshake_received = False
        self.send(msg)
