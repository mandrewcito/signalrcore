import time
from typing import Optional
from ..reconnection import ConnectionStateChecker
from ...messages.ping_message import PingMessage
from ...protocol.messagepack_protocol import MessagePackHubProtocol
from ..base_transport import BaseTransport, TransportState
from .websocket_client import WebSocketClient, SocketClosedError


class WebsocketTransport(BaseTransport):
    _client: Optional[WebSocketClient] = None

    def __init__(
            self,
            keep_alive_interval=15,
            **kwargs):
        super(WebsocketTransport, self).__init__(**kwargs)
        self.handshake_received = False
        self.connection_checker = ConnectionStateChecker(
            lambda: self.send(PingMessage()),
            keep_alive_interval
        )

    def create_client(self) -> WebSocketClient:
        return WebSocketClient(
            url=self.url,
            connection_id=self.connection_id,
            headers=self.headers,
            is_binary=type(self.protocol) is MessagePackHubProtocol,
            verify_ssl=self.verify_ssl,
            enable_trace=self.enable_trace,
            on_message=self.on_message,
            on_error=self.on_socket_error,
            on_close=self.on_socket_close,
            on_open=self.on_socket_open)

    def evaluate_handshake(self, message):
        self.logger.debug("Evaluating handshake {0}".format(message))
        msg, messages = self.protocol.decode_handshake(message)
        if msg.error is None or msg.error == "":
            self.handshake_received = True
            self._set_state(TransportState.connected)
            if self.reconnection_handler is not None:
                self.reconnection_handler.reconnecting = False
                if not self.connection_checker.running:
                    self.connection_checker.start()
        else:
            self.logger.error(msg.error)
            self.on_socket_error(msg.error)
            self.stop()
        return messages

    def on_socket_error(self, error: Exception):  # pragma: no cover
        """
        Args:
            error (Exception): websocket error

        Raises:
            HubError: [description]
        """
        self.logger.debug("-- web socket error --")
        super().on_socket_error(error)

    def on_socket_close(self):
        if not self.manually_closing and\
                self.reconnection_handler is not None\
                and not self.is_reconnecting():
            self.handle_reconnect()
            return
        self._set_state(TransportState.disconnected)

    def on_socket_open(self):
        self.logger.debug("-- web socket open --")
        self.send_handshake()

    def on_message(self, app, raw_message):
        self.logger.debug("Message received {0}".format(raw_message))
        if not self.handshake_received:
            messages = self.evaluate_handshake(raw_message)
            self._set_state(TransportState.connected)

            if len(messages) > 0:
                return self._on_message(messages)

            return []

        return self._on_message(
            self.protocol.parse_messages(raw_message))

    def send(self, message):
        self.logger.debug("Sending message {0}".format(message))
        try:
            self._client.send(
                self.protocol.encode(message),
                opcode=0x2
                if type(self.protocol) is MessagePackHubProtocol else
                0x1)
            self.connection_checker.last_message = time.time()
            if self.reconnection_handler is not None:
                self.reconnection_handler.reset()
        except (OSError, SocketClosedError) as ex:  # pragma: no cover
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
