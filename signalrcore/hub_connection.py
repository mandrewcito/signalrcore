import uuid
from .hub.base_hub_connection import BaseHubConnection
from .hub.auth_hub_connection import AuthHubConnection
from .messages.invocation_message import InvocationMessage
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
    def __init__(self, hub_url, headers=None, token=None, negotiate_headers=None):
        """
        :param hub_url: Hub url
        :param headers: heaaders on hub ws
        :param token: auth token (hub and negotiation)
        :param negotiate_headers: (negotiate headers if not None it will activate negotiation)
        """
        if hub_url is None or hub_url.strip() is "":
            raise HubConnectionError("hub_url must be a valid url.")

        self.hub_url = hub_url
        self._hub = None
        self.has_auth_configured = False
        self.token = token
        self.headers = headers
        self.negotiate_headers = negotiate_headers
        self.has_auth_configured = token is not None
        self.protocol = JsonHubProtocol()

    def build(self):
        self._hub = AuthHubConnection(self.hub_url, self.protocol, self.token, self.negotiate_headers)\
            if self.has_auth_configured else\
            BaseHubConnection(
                self.hub_url,
                self.protocol)

    def on(self, event, callback_function):
        """
        Register a callback on the specified event
        :param event: Event name
        :param callback_function: callback function, arguments will be binded
        :return:
        """
        self._hub.register_handler(event, callback_function)

    def stream(self, event, event_params, next_callback, complete_callback, error_callback):
        """
                connection.stream("Counter", 10, 500)
            .subscribe({
                next: (item) => {
                    var li = document.createElement("li");
                    li.textContent = item;
                    document.getElementById("messagesList").appendChild(li);
                },
                complete: () => {
                    var li = document.createElement("li");
                    li.textContent = "Stream completed";
                    document.getElementById("messagesList").appendChild(li);
                },
                error: (err) => {
                    var li = document.createElement("li");
                    li.textContent = err;
                    document.getElementById("messagesList").appendChild(li);
                },
        });
        """
        self._hub.stream(event, event_params, next_callback, complete_callback, error_callback)
        
    def start(self):
        self._hub.start()

    def stop(self):
        self._hub.stop()

    def send(self, method, arguments):
        if not self._hub.connection_alive:
            raise HubConnectionError("Connection is closed, cant send a message")
        if type(arguments) is not list:
            raise HubConnectionError("Arguments of a message must be a list")
        self._hub.send(InvocationMessage(
            {},
            str(uuid.uuid4()),
            method,
            arguments))
