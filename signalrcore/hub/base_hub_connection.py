"""
HubConnection(String url, Transport transport, boolean skipNegotiate, HttpClient httpClient,
Single<String> accessTokenProvider, long handshakeResponseTimeout, Map<String, String> headers)
"""

import logging
import websocket
import threading

from signalrcore.messages.message_type import MessageType


class BaseHubConnection(websocket.WebSocketApp):
    def __init__(self, url, protocol, headers={}):
        self.logger = logging.getLogger("SignalRCoreClient")
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        self.logger.addHandler(ch)
        self.url = url
        self.protocol = protocol
        self.headers = headers
        self.handshake_received = False
        self.connection_alive = False
        self.handlers = []
        super(BaseHubConnection, self).__init__(
            self.url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
            header=headers)

    def start(self):
        t = threading.Thread(target=self.run_forever)
        t.start()

    def stop(self):
        self.close()

    def register_handler(self, event, callback):
        self.handlers.append((event, callback))

    def evaluate_handshake(self, message):
        msg = self.protocol.decode_handshake(message)
        if msg.error is None or msg.error == "":
            self.handshake_received = True
            self.connection_alive = True
        else:
            self.logger.error(msg.error)
            raise ValueError("Handshake error {0}".msg.error)

    def on_open(self):
        self.logger.info("-- web socket open --")
        msg = self.protocol.handshake_message()
        self.send(msg)

    def on_close(self):
        self.logger.info("-- web socket close --")

    def on_error(self, error):
        self.logger.error("-- web socket error --")
        self.logger.error("{0}".format(error))

    def on_message(self, raw_message):
        if not self.handshake_received:
            self.evaluate_handshake(raw_message)
            return

        messages = self.protocol.parse_messages(raw_message)
        for message in messages:
            if message.type == MessageType.invocation_binding_failure:
                logging.error(message)
                continue
            if message.type == MessageType.invocation:
                fired_handlers = list(filter(lambda h: h[0] == message.target, self.handlers))
                if len(fired_handlers) == 0:
                    logging.warn("event '{0}' hasn't fire any handler".format(message.target))
                for _, handler in fired_handlers:
                    handler(message.arguments)

            if message.type == MessageType.close:
                logging.info("Close message received from server")
                self.connection_alive = False
                return
            if message.type == MessageType.completion or \
                    message.type == MessageType.stream_item or \
                    message.type == MessageType.stream_invocation or \
                    message.type == MessageType.cancel_invocation:
                raise ValueError("This client doesnt support this operation yet!")

    def send(self, message):
        super(BaseHubConnection, self).send(self.protocol.encode(message))
