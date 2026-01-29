import traceback
from typing import Optional
from ..base_transport import BaseTransport, TransportState
from .long_polling_client import\
    LongPollingBaseClient, \
    LongPollingBinaryClient, \
    LongPollingTextClient


class LongPollingTransport(BaseTransport):
    _client: Optional[LongPollingBaseClient]

    def __init__(
            self,
            **kwargs):
        super(LongPollingTransport, self).__init__(**kwargs)

        self._client_cls = LongPollingBinaryClient\
            if self.is_binary else LongPollingTextClient

    def start(self, reconnection: bool = False):

        if reconnection:
            self.negotiate()
            self._set_state(TransportState.reconnecting)
        else:
            self._set_state(TransportState.connecting)

        self.handshake_received = False
        self.logger.debug("start url:" + self.url)

        self._client = self._client_cls(
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
            self._client.close()

    def stop(self):
        self.manually_closing = True
        self.handshake_received = False
        self.dispose()

    def on_open(self):
        self.logger.debug("-- Long Polling open --")
        msg = self.protocol.handshake_message()
        self.handshake_received = False
        self._client.send(
            self.protocol.encode(msg))

    def on_close(self):
        self.logger.debug("-- Long Polling close --")
        self._set_state(TransportState.disconnected)

    def on_client_error(self, error: Exception):  # pragma: no cover
        """
        Args:
            error (Exception): websocket error

        Raises:
            HubError: [description]
        """
        self.logger.debug("-- Long Polling error --")
        self.logger.error(traceback.format_exc(10, True))
        self.logger.error("{0} {1}".format(self, error))
        self.logger.error("{0} {1}".format(error, type(error)))
        self._set_state(TransportState.disconnected)
        # raise HubError(error)

    def on_client_close(self):
        self._set_state(TransportState.disconnected)

    def on_client_open(self):
        self.on_open()

    def evaluate_handshake(self, message):

        self.logger.debug("Evaluating handshake {0}".format(message))

        handshake_response, messages = self.protocol.decode_handshake(
            message
        )

        self.handshake_received = handshake_response.error is None

        return messages

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
                self.protocol.encode(message))
        except OSError as ex:
            self.handshake_received = False
            self.logger.warning("Connection closed {0}".format(ex))
        except Exception as ex:
            raise ex
