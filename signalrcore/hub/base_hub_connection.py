import uuid
import copy
import ssl
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
from ..protocol.protocol_factory import ProtocolFactory
from ..transport.transport_factory import TransportFactory
from .negotiation import NegotiateResponse, NegotiationHandler
from ..types import HttpTransportType, HubProtocolEncoding
from ..messages.base_message import BaseMessage
from ..messages.completion_message import CompletionMessage
from ..messages.stream_item_message import StreamItemMessage
from ..messages.cancel_invocation_message import CancelInvocationMessage
from ..messages.ping_message import PingMessage
from ..messages.ack_message import AckMessage
from ..messages.sequence_message import SequenceMessage
from ..messages.close_message import CloseMessage


class InvocationResult(object):
    def __init__(self, invocation_id) -> None:
        self.invocation_id = invocation_id
        self.message = None


class HubCallbacks(object):
    on_open: Callable
    on_close: Callable
    on_error: Callable[[Exception], None]
    on_reconnect: Callable

    def __init__(self):
        self.logger = Helpers.get_logger()
        self._on_open = lambda: self.logger.info("on_open not defined")
        self._on_close = lambda: self.logger.info("on_close not defined")
        self._on_error = lambda error: self.logger.info(
            "on_error not defined {0}".format(error))
        self._on_reconnect = lambda: self.logger.info(
            "on_reconnect not defined")

    def on_open(self):
        return self._on_open()

    def on_close(self):
        return self._on_close()

    def on_error(self, error: Exception):
        return self._on_error(error)

    def on_reconnect(self):
        return self._on_reconnect()


class BaseHubConnection(object):
    url: str
    headers: dict
    token: str
    ssl_context: ssl.SSLContext
    protocol: BaseHubProtocol = None
    transport: BaseTransport = None
    preferred_transport: Optional[HttpTransportType] = None
    preferred_protocol: Optional[HubProtocolEncoding] = None

    def __init__(
            self,
            url: str,
            preferred_protocol: Optional[HubProtocolEncoding] = None,
            preferred_transport: Optional[HttpTransportType] = None,
            skip_negotiation=False,
            headers=None,
            ssl_context: ssl.SSLContext = ssl.create_default_context(),
            protocol=None,
            proxies: dict = {},
            **kwargs):
        self.preferred_protocol = preferred_protocol
        self.preferred_transport = preferred_transport
        self.kwargs = kwargs
        self.url = url
        self.ssl_context = ssl_context
        self.proxies = proxies
        self.token = None
        self._selected_protocol = protocol

        if headers is None:
            self.headers = dict()  # pragma: no cover
        else:
            self.headers = headers

        self.logger = Helpers.get_logger()
        self.handlers = defaultdict(list)
        self.stream_handlers = defaultdict(list)
        self.skip_negotiation = skip_negotiation
        self._callbacks = HubCallbacks()
        self._receive_sequence_id = 0
        self._send_sequence_id = 0

    def _negotiate(self) -> NegotiateResponse:
        """Negotiates connection with the server, do not call it
        manually.
        Updates url and headers if is necessary
        Returns:
            NegotiateResponse: Negotiation response result.
        """
        handler = NegotiationHandler(
            self.url,
            self.headers,
            self.proxies,
            self.ssl_context,
            self.skip_negotiation
        )

        (url, headers, response) = handler.negotiate()

        self.url = url
        self.headers = copy.deepcopy(headers)

        return response

    def start(self) -> bool:
        """Starts the connection

        Returns:
            bool: True if connection stars successfully, False
            if connection cant start or is already connected
        """
        if self.transport is not None and self.transport.is_connected():
            self.logger.warning("Already connected unable to start")
            return False

        self.logger.debug("Connection started")

        negotiate_response = self._negotiate()

        self.protocol = ProtocolFactory.create(
                self.preferred_transport,
                self.preferred_protocol,
                negotiate_response)\
            if self._selected_protocol is None else\
            self._selected_protocol

        def wrapped_on_reconnect():
            self.logger.debug("Reconnecting: Sending SequenceMessage")
            self.transport.send(SequenceMessage(self._receive_sequence_id))
            self._callbacks.on_reconnect()

        self.transport = TransportFactory.create(
            negotiate_response,
            self.preferred_transport,
            url=self.url,
            protocol=self.protocol,
            headers=self.headers,
            token=self.token,
            skip_negotiation=self.skip_negotiation,
            connection_id=negotiate_response.get_id(),
            ssl_context=self.ssl_context,
            proxies=self.proxies,
            on_close=self._callbacks.on_close,
            on_open=self._callbacks.on_open,
            on_reconnect=wrapped_on_reconnect,
            on_message=self.on_message,
            **self.kwargs
        )

        # On start, reset sequence
        self._receive_sequence_id = 0
        self._send_sequence_id = 0

        # Note: If this is a reconnect we'd need to emit SequenceMessage
        # Actually start will re-negotiate,
        # handle reconnect logic separately if needed
        # Or if we just need to send it on actual reconnect event:
        # For now, start is fresh connection.

        return self.transport.start()

    def stop(self) -> None:
        """Stops the connection

        Returns:
            None
        """
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
        self._callbacks._on_close = callback

    def on_open(self, callback) -> None:
        """Configures on_open connection callback.
            It will be raised on connection open event
        connection.on_open(lambda: print(
            "connection opened "))
        Args:
            callback (function): function without params
        """
        self._callbacks._on_open = callback

    def on_error(self, callback) -> None:
        """Configures on_error connection callback. It will be raised
            if any hub method throws an exception.
        connection.on_error(lambda data:
            print(f"An exception was thrown closed{data.error}"))
        Args:
            callback (function): function with one parameter.
                A CompletionMessage object.
        """
        self._callbacks._on_error = callback

    def on_reconnect(self, callback) -> None:
        """Configures on_reconnect reconnection callback.
            It will be raised on reconnection event
        connection.on_reconnect(lambda: print(
            "connection lost, reconnection in progress "))
        Args:
            callback (function): function without params
        """
        self._callbacks._on_reconnect = callback

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
            on_invocation: Optional[Callable[[List[CompletionMessage]], None]] = None,  # noqa: E501
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

            self._send_sequence_id += 1
            self.transport.send(message)
            result.message = message

        if type(arguments) is Subject:
            arguments.connection = self
            arguments.target = method
            arguments.start()
            result.invocation_id = arguments.invocation_id
            result.message = arguments

        return result

    def __on_invocation_message(self, message: InvocationMessage) -> None:  # 1
        message: InvocationMessage
        fired_handlers = self.handlers.get(message.target, [])

        if len(fired_handlers) == 0:
            self.logger.info(
                f"Event '{message.target}' hasn't fired any handler")

        for handler in fired_handlers:
            handler(message.arguments)

    def __on_stream_item_message(
            self, message: StreamItemMessage) -> None:  # 2
        fired_handlers = self.stream_handlers.get(
            message.invocation_id, [])

        if len(fired_handlers) == 0:
            self.logger.warning(
                "id '{0}' hasn't fire any stream handler".format(
                    message.invocation_id))

        for handler in fired_handlers:
            handler.next_callback(message.item)

    def __on_completion_message(self, message: CompletionMessage) -> None:  # 3
        if message.error is not None and len(message.error) > 0:
            self._callbacks.on_error(message)
        else:
            # Send callbacks
            fired_handlers: List[StreamHandler] = self.stream_handlers.get(
                message.invocation_id, [])

            # Stream callbacks
            for handler in fired_handlers:
                handler: StreamHandler
                handler.complete_callback(message)

        # unregister handler
        if message.invocation_id in self.stream_handlers:
            del self.stream_handlers[message.invocation_id]

    def __on_stream_invocation_message(
            self, message: StreamInvocationMessage) -> None:  # 4 # pragma: no cover # noqa: E501
        self.logger.debug(f"Stream invocation message {message}")

    def __on_cancel_invocation_message(
            self, message: CancelInvocationMessage) -> None:  # 5 # pragma: no cover # noqa: E501
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

    def __on_ping_message(
            self, message: PingMessage) -> None:  # 6
        self.logger.debug(f"Ping message {message}")

    def __on_close_message(
            self, message: CloseMessage) -> None:  # 6
        self.logger.info(f"Close message received from server {message}")
        self.transport.dispose()

    def __on_ack_message(
            self, message: AckMessage) -> None:  # pragma: no cover # 8
        self.logger.debug(f"Ack message {message}")

    def __on_sequence_message(
            self, message: SequenceMessage) -> None:  # pragma: no cover # 9
        self.logger.debug(f"Sequence message {message}")

    def __on_binding_failure(self, message) -> None:  # -1  # pragma: no cover # noqa: E501
        self.logger.error(message)
        self._callbacks.on_error(message)

    def on_message(self, messages: List[BaseMessage]) -> None:
        for message in messages:
            self.logger.debug(message)

            is_trackable = message.type in [
                MessageType.invocation,
                MessageType.stream_item,
                MessageType.completion,
                MessageType.stream_invocation,
                MessageType.cancel_invocation
            ]

            if is_trackable:
                self._receive_sequence_id += 1

            if message.type == MessageType.invocation_binding_failure:  # pragma: no cover # noqa: E501
                self.__on_binding_failure(message)
            elif message.type == MessageType.invocation:
                self.__on_invocation_message(message)
            elif message.type == MessageType.stream_item:  # 2
                self.__on_stream_item_message(message)
            elif message.type == MessageType.completion:  # 3
                self.__on_completion_message(message)
            elif message.type == MessageType.stream_invocation:  # 4 # pragma: no cover # noqa: E501
                self.__on_stream_invocation_message(message)
            elif message.type == MessageType.cancel_invocation:  # 5 # pragma: no cover # noqa: E501
                self.__on_cancel_invocation_message(message)
            elif message.type == MessageType.ping:  # 6
                self.__on_ping_message(message)
            elif message.type == MessageType.close:  # 7
                self.__on_close_message(message)
                return
            elif message.type == MessageType.ack:  # pragma: no cover  # 8
                self.__on_ack_message(message)
            elif message.type == MessageType.sequence:  # pragma: no cover # 9
                self.__on_sequence_message(message)

            if is_trackable:
                self.transport.send(AckMessage(self._receive_sequence_id))

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
        self._send_sequence_id += 1
        self.transport.send(
            StreamInvocationMessage(
                invocation_id,
                event,
                event_params,
                headers=self.headers))
        return stream_obj
