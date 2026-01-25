import traceback
import time

from typing import Optional

from ..base_transport import BaseTransport
from .sse_client import SSEClient
from ..base_transport import TransportState
from ..reconnection import ConnectionStateChecker
from ...messages.ping_message import PingMessage
from ...protocol.json_hub_protocol import JsonHubSseProtocol


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

    def start(self, reconnection: bool = False):
        if reconnection:
            self.negotiate()
            self._set_state(TransportState.reconnecting)
        else:
            self._set_state(TransportState.connecting)

        self.logger.debug("start url:" + self.url)

        self.protocol = JsonHubSseProtocol()

        self._client = SSEClient(
            url=self.url,
            connection_id=self.connection_id,
            headers=self.headers,
            proxies=self.proxies,
            verify_ssl=self.verify_ssl,
            enable_trace=self.enable_trace,
            on_message=self.on_message,
            on_open=self.on_client_open,
            on_close=self.on_client_close,
            on_error=self.on_client_error
        )

        self._client.connect()

        return True

    def dispose(self):
        if self.is_connected():
            self.keep_alive_interval = 0
            self.connection_checker.stop()
            self._client.close()

    def stop(self):
        self.manually_closing = True
        self.handshake_received = False
        self.dispose()

    def on_open(self):
        self.logger.debug("-- SSE open --")
        msg = self.protocol.handshake_message()
        self.handshake_received = False
        self.send(msg)
        self._client.send(
            self.protocol.encode(msg) + b"\x1e",
            {"Content-Type": "application/json"})

    def on_close(self):
        self.logger.debug("-- SSE close --")
        self._set_state(TransportState.disconnected)

    def on_client_error(self, error: Exception):  # pragma: no cover
        """
        Args:
            error (Exception): websocket error

        Raises:
            HubError: [description]
        """
        self.logger.debug("-- SSE error --")
        self.logger.error(traceback.format_exc(10, True))
        self.logger.error("{0} {1}".format(self, error))
        self.logger.error("{0} {1}".format(error, type(error)))
        self._set_state(TransportState.disconnected)
        # raise HubError(error)

    def on_client_close(self):
        if self.reconnection_handler is not None\
                and not self.is_reconnecting()\
                and not self.manually_closing:
            self.handle_reconnect()
            return
        self._set_state(TransportState.disconnected)

    def on_client_open(self):
        self.on_open()

    def evaluate_handshake(self, message):
        self.logger.debug("Evaluating handshake {0}".format(message))

        handshake_response, messages = self.protocol.decode_handshake(
            message
        )

        self.handshake_received = handshake_response.error is None

        if self.handshake_received and not self.connection_checker.running:
            self.connection_checker.start()

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

    def handle_reconnect(self):
        if self.is_reconnecting() or self.manually_closing:
            return  # pragma: no cover

        self.reconnection_handler.reconnecting = True
        self._set_state(TransportState.reconnecting)
        try:
            self._client.dispose()
            self.start(reconnection=True)
        except Exception as ex:
            self.logger.error(ex)
            sleep_time = self.reconnection_handler.next()
            self.deferred_reconnect(sleep_time)

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
