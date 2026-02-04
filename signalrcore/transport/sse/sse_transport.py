import time

from typing import Optional

from ..base_transport import BaseTransport
from .sse_client import SSEClient
from ..base_transport import TransportState
from ..reconnection import ConnectionStateChecker
from ...messages.ping_message import PingMessage
from ..sockets.errors import SocketClosedError


class SSETransport(BaseTransport):
    _client: Optional[SSEClient]

    def __init__(
            self,
            keep_alive_interval=15,
            **kwargs):
        super(SSETransport, self).__init__(**kwargs)

        self.keep_alive_interval = keep_alive_interval
        self.connection_checker = ConnectionStateChecker(
            self.connection_check,
            keep_alive_interval
        )

        self.manually_closing = False
        self.connection_alive = False

    def connection_check(self):
        time_without_messages =\
            time.time() - self.connection_checker.last_message

        self.connection_alive =\
            time_without_messages < self.keep_alive_interval

        if self._client.is_connection_closed()\
                and self.reconnection_handler is None:
            self.connection_checker.stop()
            self._set_state(TransportState.disconnected)
            return

        # Connection closed
        self.handle_reconnect()  # pragma: no cover

        if self.connection_alive:
            self.send(PingMessage())

    def create_client(self) -> SSEClient:
        return SSEClient(
            url=self.url,
            connection_id=self.connection_id,
            headers=self.headers,
            proxies=self.proxies,
            ssl_context=self.ssl_context,
            enable_trace=self.enable_trace,
            on_message=self.on_message,
            on_open=self.on_client_open,
            on_close=self.on_client_close,
            on_error=self.on_client_error
        )

    def on_client_error(self, error: Exception):  # pragma: no cover
        """
        Args:
            error (Exception): websocket error

        Raises:
            HubError: [description]
        """
        if self.manually_closing and type(error) is SocketClosedError:
            return

        self.logger.debug("-- SSE error --")
        super().on_socket_error(error)

    def on_client_close(self):
        did_i_reconnect = self.reconnection_handler is not None \
            and (
                not self.manually_closing
                and not self.reconnection_handler.reconnecting
                )

        if not did_i_reconnect or self.manually_closing:
            self.logger.debug("-- SSE close --")
            self._set_state(TransportState.disconnected)
            return
        self.handle_reconnect()

    def on_client_open(self):
        self.logger.debug("-- SSE open --")
        self.send_handshake()

    def evaluate_handshake(self, message):
        self.logger.debug("Evaluating handshake {0}".format(message))

        handshake_response, messages = self.protocol.decode_handshake(
            message
        )

        self.handshake_received = handshake_response.error is None

        if self.handshake_received and not self.connection_checker.running:
            self.connection_checker.start()
            self.connection_checker.last_message = time.time()

        return messages

    def on_message(self, app, raw_message):
        self.logger.debug("Message received {0}".format(raw_message))

        self.connection_checker.last_message = time.time()

        if not self.handshake_received:
            messages = self.evaluate_handshake(raw_message)
            self._set_state(TransportState.connected)

            if len(messages) > 0:
                return self._on_message(messages)
            return []

        if self.reconnection_handler is not None:
            self.reconnection_handler.reset()

        return self._on_message(
            self.protocol.parse_messages(raw_message))

    def send(self, message):
        self.logger.debug("Sending message {0}".format(message))
        try:
            self._client.send(
                self.protocol.encode(message))
        except OSError as ex:  # pragma: no cover
            self.handshake_received = False  # pragma: no cover
            self.logger.warning("Connection closed {0}".format(ex))
            # pragma: no cover
            if self.reconnection_handler is None:  # pragma: no cover
                self._set_state(TransportState.disconnected)
                # pragma: no cover
                raise ValueError(str(ex))  # pragma: no cover
            # Connection closed
            self.handle_reconnect()  # pragma: no cover
        except Exception as ex:  # pragma: no cover
            raise ex  # pragma: no cover
