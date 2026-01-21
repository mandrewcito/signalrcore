import uuid
from typing import Callable, List, Union, Optional
from signalrcore.messages.message_type import MessageType
from signalrcore.messages.stream_invocation_message\
    import StreamInvocationMessage
from .errors import HubConnectionError
from signalrcore.helpers import Helpers
from .handlers import StreamHandler, InvocationHandler
from ..transport.base_transport import BaseTransport
from ..subject import Subject
from ..messages.invocation_message import InvocationMessage
from collections import defaultdict
from ..protocol.base_hub_protocol import BaseHubProtocol
from ..transport.transport_factory import TransportFactory
from .negotiation import NegotiateResponse, NegotiationHandler


class InvocationResult(object):
    def __init__(self, invocation_id) -> None:
        self.invocation_id = invocation_id
        self.message = None


class HubCallbacks(object):
    on_open: Callable
    on_close: Callable
    on_error: Callable
    on_reconnect: Callable

    def __init__(self):
        self.logger = Helpers.get_logger()
        self.on_open = lambda: self.logger.info("on_open not defined")
        self.on_close = lambda: self.logger.info("on_close not defined")
        self.on_error = lambda error: self.logger.info(
            "on_error not defined {0}".format(error))
        self.on_reconnect = lambda: self.logger.info(
            "on_reconnect not defined")


class BaseHubConnection(object):
    transport: BaseTransport = None
    url: str
    protocol: BaseHubProtocol
    headers: dict
    token: str
    verify_ssl: bool

    def __init__(
            self,
            url: str,
            protocol: BaseHubProtocol,
            skip_negotiation=False,
            headers=None,
            verify_ssl=False,
            proxies: dict = {},
            **kwargs):
        self.kwargs = kwargs
        self.url = url
        self.verify_ssl = verify_ssl
        self.protocol = protocol
        self.proxies = proxies
        self.token = None

        if headers is None:
            self.headers = dict()
        else:
            self.headers = headers

        self.logger = Helpers.get_logger()
        self.handlers = defaultdict(list)
        self.stream_handlers = defaultdict(list)
        self.skip_negotiation = skip_negotiation
        self._callbacks = HubCallbacks()

    def negotiate(self) -> NegotiateResponse:
        handler = NegotiationHandler(
            self.url,
            self.headers,
            self.proxies,
            self.verify_ssl
        )
        self.url, self.headers, response = handler.negotiate()
        return response

    def start(self) -> None:
        if self.transport is not None and self.transport.is_connected():
            self.logger.warning("Already connected unable to start")
            return False

        self.logger.debug("Connection started")
        available_transports = None

        if not self.skip_negotiation:
            response = self.negotiate()
            available_transports = response.available_transports

        self.transport = TransportFactory.create(
            available_transports,
            url=self.url,
            protocol=self.protocol,
            headers=self.headers,
            token=self.token,
            verify_ssl=self.verify_ssl,
            proxies=self.proxies,
            on_message=self.on_message,
            **self.kwargs
        )

        # Register transport callbacks
        self.transport.on_close_callback(self._callbacks.on_close)
        self.transport.on_open_callback(self._callbacks.on_open)
        self.transport.on_reconnect_callback(self._callbacks.on_reconnect)

        return self.transport.start()

    def stop(self) -> None:
        self.logger.debug("Connection stop")
        if self.transport is not None:
            return self.transport.stop()

    def on_close(self, callback) -> None:
        """Configures on_close connection callback.
            It will be raised on connection closed event
        connection.on_close(lambda: print("connection closed"))
        Args:
            callback (function): function without params
        """
        self._callbacks.on_close = callback

    def on_open(self, callback) -> None:
        """Configures on_open connection callback.
            It will be raised on connection open event
        connection.on_open(lambda: print(
            "connection opened "))
        Args:
            callback (function): function without params
        """
        self._callbacks.on_open = callback

    def on_error(self, callback) -> None:
        """Configures on_error connection callback. It will be raised
            if any hub method throws an exception.
        connection.on_error(lambda data:
            print(f"An exception was thrown closed{data.error}"))
        Args:
            callback (function): function with one parameter.
                A CompletionMessage object.
        """
        self._callbacks.on_error = callback

    def on_reconnect(self, callback) -> None:
        """Configures on_reconnect reconnection callback.
            It will be raised on reconnection event
        connection.on_reconnect(lambda: print(
            "connection lost, reconnection in progress "))
        Args:
            callback (function): function without params
        """
        self._callbacks.on_reconnect = callback

    def on(self, event, callback_function: Callable) -> None:
        """Register a callback on the specified event
        Args:
            event (string):  Event name
            callback_function (Function): callback function,
                arguments will be bound
        """
        self.logger.debug("Handler registered started {0}".format(event))
        self.handlers[event].append(callback_function)

    def unsubscribe(self, event, callback_function: Callable) -> None:
        """Removes a callback from the specified event
        Args:
            event (string): Event name
            callback_function (Function): callback function,
                arguments will be bound
        """
        self.logger.debug("Handler removed {0}".format(event))

        self.handlers[event].remove(callback_function)

        if len(self.handlers[event]) == 0:
            del self.handlers[event]

    def send(self, method, arguments, on_invocation=None, invocation_id=None)\
            -> InvocationResult:
        """invokes a server function
        Deprecated: 0.96
            Use invoke instead
        Args:
            method (string): Method name
            arguments (list|Subject): Method parameters
            on_invocation (function, optional): On invocation send callback
                will be raised on send server function ends. Defaults to None.
            invocation_id (string, optional): Override invocation ID.
                Exceptions thrown by the hub will use this ID,
                making it easier to handle with the on_error call.

        Raises:
            HubConnectionError: If hub is not ready to send
            TypeError: If arguments are invalid list or Subject
        """
        return self.invoke(method, arguments, on_invocation, invocation_id)

    def invoke(
            self,
            method: str,
            arguments: Union[List, Subject],
            on_invocation: Optional[Callable] = None,
            invocation_id: Optional[str] = None)\
            -> InvocationResult:
        """invokes a server function

        Args:
            method (string): Method name
            arguments (list|Subject): Method parameters
            on_invocation (function, optional): On invocation send callback
                will be raised on send server function ends. Defaults to None.
            invocation_id (string, optional): Override invocation ID.
                Exceptions thrown by the hub will use this ID,
                making it easier to handle with the on_error call.

        Raises:
            HubConnectionError: If hub is not ready to send
            TypeError: If arguments are invalid list or Subject
        """
        if invocation_id is None:
            invocation_id = str(uuid.uuid4())

        if self.transport is None or not self.transport.is_running():
            raise HubConnectionError(
                "Cannot connect to SignalR hub. Unable to transmit messages")

        if type(arguments) is not list and type(arguments) is not Subject:
            raise TypeError("Arguments of a message must be a list or subject")

        result = InvocationResult(invocation_id)

        if type(arguments) is list:
            message = InvocationMessage(
                invocation_id,
                method,
                arguments,
                headers=self.headers)

            if on_invocation:
                self.stream_handlers[message.invocation_id].append(
                    InvocationHandler(
                        message.invocation_id,
                        on_invocation))

            self.transport.send(message)
            result.message = message

        if type(arguments) is Subject:
            arguments.connection = self
            arguments.target = method
            arguments.start()
            result.invocation_id = arguments.invocation_id
            result.message = arguments

        return result

    def on_message(self, messages) -> None:
        for message in messages:
            if message.type == MessageType.invocation_binding_failure:
                self.logger.error(message)
                self._callbacks.on_error(message)
                continue

            if message.type == MessageType.ping:
                continue

            if message.type == MessageType.invocation:

                fired_handlers = self.handlers.get(message.target, [])

                if len(fired_handlers) == 0:
                    self.logger.debug(
                        f"event '{message.target}' hasn't fired any handler")

                for handler in fired_handlers:
                    handler(message.arguments)

            if message.type == MessageType.close:
                self.logger.info("Close message received from server")
                self.transport.dispose()
                return

            if message.type == MessageType.completion:
                if message.error is not None and len(message.error) > 0:
                    self._callbacks.on_error(message)

                # Send callbacks
                fired_handlers = self.stream_handlers.get(
                    message.invocation_id, [])

                # Stream callbacks
                for handler in fired_handlers:
                    handler.complete_callback(message)

                # unregister handler
                if message.invocation_id in self.stream_handlers:
                    del self.stream_handlers[message.invocation_id]

            if message.type == MessageType.stream_item:
                fired_handlers = self.stream_handlers.get(
                    message.invocation_id, [])

                if len(fired_handlers) == 0:
                    self.logger.warning(
                        "id '{0}' hasn't fire any stream handler".format(
                            message.invocation_id))

                for handler in fired_handlers:
                    handler.next_callback(message.item)

            if message.type == MessageType.stream_invocation:
                pass

            if message.type == MessageType.cancel_invocation:
                fired_handlers = self.stream_handlers.get(
                    message.invocation_id, [])

                if len(fired_handlers) == 0:
                    self.logger.warning(
                        "id '{0}' hasn't fire any stream handler".format(
                            message.invocation_id))

                for handler in fired_handlers:
                    handler.error_callback(message)

                # unregister handler
                if message.invocation_id in self.stream_handlers:
                    del self.stream_handlers[message.invocation_id]

    def stream(self, event, event_params) -> StreamHandler:
        """Starts server streaming
            connection.stream(
            "Counter",
            [len(self.items), 500])\
            .subscribe({
                "next": self.on_next,
                "complete": self.on_complete,
                "error": self.on_error
            })
        Args:
            event (string): Method Name
            event_params (list): Method parameters

        Returns:
            [StreamHandler]: stream handler
        """
        invocation_id = str(uuid.uuid4())
        stream_obj = StreamHandler(event, invocation_id)
        self.stream_handlers[invocation_id].append(stream_obj)
        self.transport.send(
            StreamInvocationMessage(
                invocation_id,
                event,
                event_params,
                headers=self.headers))
        return stream_obj
