import enum
import traceback
import threading
import time
import ssl
from typing import Callable, Dict, Optional
from ..helpers import Helpers
from ..transport.base_reconnection import BaseReconnection
from ..protocol.base_hub_protocol import BaseHubProtocol
from ..hub.negotiation import NegotiateResponse, NegotiationHandler
from .base_client import BaseClient
from ..messages.ping_message import PingMessage
from .reconnection import ConnectionStateChecker
from .sockets.utils import create_ssl_context


class TransportState(enum.Enum):
    connecting = 0  # connection established, handshake not received
    connected = 1  # connection established, handshake received
    reconnecting = 2  # connection not established, reconnecting
    disconnected = 3  # connection not established


RECONNECTION_THREAD_NAME = "Signalrcore reconnection"


class BaseTransport(object):
    _client: Optional[BaseClient]
    connection_checker: ConnectionStateChecker
    manually_closing: bool
    connection_alive: bool = False

    def __init__(
            self,
            url: str = None,
            connection_id: str = None,
            is_binary: bool = False,
            skip_negotiation: bool = False,
            token: Optional[str] = None,
            headers: Optional[Dict] = None,
            proxies: Optional[Dict] = None,
            ssl_context: ssl.SSLContext = None,
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
        self.enable_trace = enable_trace
        self.skip_negotiation = skip_negotiation
        self.ssl_context = ssl_context\
            if ssl_context is not None else\
            create_ssl_context(True)
        self.connection_id = connection_id
        self.proxies = proxies
        self.protocol = protocol

        self.logger = Helpers.get_logger()

        self._on_message = on_message
        self._on_open = on_open
        self._on_close = on_close
        self._on_reconnect = on_reconnect

        self.state = TransportState.disconnected
        self.handshake_received = False
        self.reconnection_handler = reconnection_handler
        self._client = None
        self.manually_closing = False
        self._reconnection_lock = threading.Lock()
        self._reconnect_thread = None
        self._reconnect_pending = False

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
            self.ssl_context,
            self.skip_negotiation
        )

        self.url, self.headers, response = handler.negotiate()
        self.connection_id = response.get_id()

        return response

    def create_client(self) -> BaseClient:  # pragma: no cover
        raise NotImplementedError()

    def start(self, reconnection: bool = False):
        if not reconnection:
            # A previous stop() must not poison manual restarts.
            self.manually_closing = False
            if self.reconnection_handler is not None:
                self.reconnection_handler.reset()

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

            if self._client is not None:
                self._client.close()

    def stop(self):
        if self.is_disconnected():
            return

        # Set the flag first: close callbacks must not start a
        # reconnection while the connection is being stopped manually.
        self.manually_closing = True
        self.handshake_received = False

        if self.reconnection_handler is not None:
            self.reconnection_handler.reconnecting = False

        try:
            self.dispose()
        finally:
            # stop() may be called while reconnecting, when the client
            # was already disposed and no close callback fires. Make
            # sure the transport never stays in the reconnecting state.
            self._set_state(TransportState.disconnected)

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

    def deferred_reconnect(self, sleep_time):  # pragma: no cover
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
        if self.manually_closing or self.reconnection_handler is None:
            return False

        if self._client is None or not self._client.is_connection_closed():
            return False

        with self._reconnection_lock:
            loop_alive = self._reconnect_thread is not None\
                and self._reconnect_thread.is_alive()

        if loop_alive and self.is_reconnecting():
            # Duplicate close event or connection-check polling while
            # a reconnection loop is already running.
            return True

        self.reconnection_handler.reconnecting = True

        # Set the state synchronously before spawning the thread so
        # that concurrent callers do not start several loops.
        self._set_state(TransportState.reconnecting)

        with self._reconnection_lock:
            if self._reconnect_thread is not None\
                    and self._reconnect_thread.is_alive():
                # The connection dropped again after a successful
                # reconnection, make the running loop retry.
                self._reconnect_pending = True
                return True

            self._reconnect_pending = False
            self._reconnect_thread = threading.Thread(
                target=self._reconnect_loop,
                name=RECONNECTION_THREAD_NAME)
            self._reconnect_thread.daemon = True
            self._reconnect_thread.start()

        return True

    def _dispose_current_client(self):
        if self._client is None:  # pragma: no cover
            return
        try:
            self._client.dispose()
        except Exception as ex:  # pragma: no cover
            self.logger.debug(f"Error disposing old client: {ex}")

    def _reconnect_loop(self):
        try:
            while not self.manually_closing:
                # Release the dead client resources before creating
                # a new one.
                self._dispose_current_client()

                try:
                    sleep_time = self.reconnection_handler.next()
                except ValueError as ex:
                    # Max attempts / intervals reached, give up.
                    self.logger.error(f"Reconnection failed: {ex}")
                    self.reconnection_handler.reconnecting = False
                    self.connection_checker.stop()
                    self._set_state(TransportState.disconnected)
                    return

                if self.manually_closing:  # pragma: no cover
                    return

                time.sleep(sleep_time)

                if self.manually_closing:  # pragma: no cover
                    return

                try:
                    self.start(reconnection=True)
                except Exception as ex:
                    self.logger.warning(
                        f"Reconnection attempt failed: {ex}")
                    continue

                # A close event may have arrived while the connection
                # was being established; retry instead of losing it.
                with self._reconnection_lock:
                    pending = self._reconnect_pending
                    self._reconnect_pending = False

                if pending or self.is_disconnected():
                    # The connection dropped while it was being
                    # established; keep retrying.
                    continue

                return
        finally:
            with self._reconnection_lock:
                if self._reconnect_thread is threading.current_thread():
                    self._reconnect_thread = None
                    self._reconnect_pending = False

    def send_handshake(self):
        msg = self.protocol.handshake_message()
        self.handshake_received = False
        self.send(msg)
