from .hub.base_hub_connection import BaseHubConnection
from .hub.auth_hub_connection import AuthHubConnection
from .messages.message import Message
from .messages.message_type import MessageType
from .protocol.json_hub_protocol import JsonHubProtocol


class HubConnectionError(ValueError):
    pass


class HubConnection(object):
    """
    Hub connection class, manages handshake and messaging

    Args:
        hub_url: SignalR core url

    Raises:
        HubConnectionError: Raises an Exception if url is empty or None
    """
    def __init__(self, hub_url):

        if hub_url is None or hub_url.strip() is "":
            raise HubConnectionError("hub_url must be a valid url.")

        self.hub_url = hub_url
        self._hub = None
        self.has_auth_configured = False
        self.protocol = JsonHubProtocol()

    def build(self):
        self._hub = AuthHubConnection()\
            if self.has_auth_configured else\
            BaseHubConnection(
                self.hub_url,
                self.protocol
            )

    def auth(self):
        self.has_auth_configured = True

    def on(self, event, callback_function):
        self._hub.register_handler(event, callback_function)

    def start(self):
        self._hub.start()

    def stop(self):
        self._hub.stop()

    def send(self, method, arguments):
        if not self._hub.connection_alive:
            raise HubConnectionError("Connection is closed, cant send a message")
        if type(arguments) is not list:
            raise HubConnectionError("Arguments of a message must be a list")
        self._hub.send(Message(
            MessageType.invocation.value,
            None,
            method,
            arguments))
