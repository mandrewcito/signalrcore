import uuid
from typing import Awaitable, Callable, List, Optional, Union

from ...hub.base_hub_connection import (
    BaseHubConnection,
    InvocationResult,
)
from ...hub.errors import HubConnectionError
from ...messages.ack_message import AckMessage
from ...messages.base_message import BaseMessage
from ...messages.cancel_invocation_message import CancelInvocationMessage
from ...messages.close_message import CloseMessage
from ...messages.completion_message import CompletionMessage
from ...messages.invocation_message import InvocationMessage
from ...messages.message_type import MessageType
from ...messages.ping_message import PingMessage
from ...messages.sequence_message import SequenceMessage
from ...messages.stream_invocation_message import StreamInvocationMessage
from ...messages.stream_item_message import StreamItemMessage
from ...subject import Subject
from ...transport.base_transport import TransportState  # noqa: F401
from ..subject import AIOSubject
from ..transport.base_transport import AIOBaseTransport
from ..utils import call_callback
from .aio_connection_mixin import AIO_CONNECTION_TIMEOUT  # noqa: F401
from .aio_connection_mixin import AIOConnectionMixin
from .handlers import AIOInvocationHandler, AIOStreamHandler


class AIOBaseHubConnection(AIOConnectionMixin, BaseHubConnection):
    """Asyncio SignalR hub connection.

    All network operations (``start``, ``stop``, ``invoke``, ``send`` and
    ``stream``) are coroutines and must be awaited. Event callbacks may be
    plain functions or coroutine functions.
    """

    transport: Optional[AIOBaseTransport] = None

    async def send(
            self,
            method: str,
            arguments: Union[List, AIOSubject],
            on_invocation: Optional[Callable[
                [List[CompletionMessage]], Awaitable[None]]] = None,
            invocation_id: str = None) -> InvocationResult:
        """Invokes a server function.

        Deprecated: 0.96
            Use invoke instead
        """
        return await self.invoke(
            method, arguments, on_invocation, invocation_id)

    async def invoke(
            self,
            method: str,
            arguments: Union[List, AIOSubject],
            on_invocation: Optional[Callable[
                [List[CompletionMessage]], Awaitable[None]]] = None,
            invocation_id: Optional[str] = None) -> InvocationResult:
        """Invokes a server function.

        Args:
            method (string): Method name
            arguments (list|AIOSubject): Method parameters. Use
                :class:`AIOSubject` for client to server streaming.
            on_invocation (function, optional): On invocation send callback
                will be raised on send server function ends. It may be a
                plain function or a coroutine function.
            invocation_id (string, optional): Override invocation ID.

        Raises:
            HubConnectionError: If hub is not ready to send
            TypeError: If arguments are invalid list or AIOSubject
        """
        if invocation_id is None:
            invocation_id = str(uuid.uuid4())

        if self.transport is None or not self.transport.is_running():
            raise HubConnectionError(
                "Cannot connect to SignalR hub. Unable to transmit messages")

        if isinstance(arguments, Subject):
            raise TypeError(
                "Use AIOSubject with asyncio hub connections")

        if type(arguments) is not list\
                and not isinstance(arguments, AIOSubject):
            raise TypeError(
                "Arguments of a message must be a list or AIOSubject")

        result = InvocationResult(invocation_id)

        if type(arguments) is list:
            message = InvocationMessage(
                invocation_id,
                method,
                arguments,
                headers=self.headers)

            if on_invocation:
                self.stream_handlers[message.invocation_id].append(
                    AIOInvocationHandler(
                        message.invocation_id,
                        on_invocation))

            await self.transport.send(message)
            result.message = message

        if isinstance(arguments, AIOSubject):
            arguments.connection = self
            arguments.target = method
            await arguments.start()
            result.invocation_id = arguments.invocation_id
            result.message = arguments

        return result

    async def stream(self, event, event_params) -> AIOStreamHandler:
        """Starts server streaming.

        connection.stream("Counter", [10, 500]).subscribe({
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
        if self.transport is None or not self.transport.is_running():
            raise HubConnectionError(
                "Cannot connect to SignalR hub. Unable to transmit messages")

        invocation_id = str(uuid.uuid4())
        stream_obj = AIOStreamHandler(event, invocation_id)
        self.stream_handlers[invocation_id].append(stream_obj)

        await self.transport.send(
            StreamInvocationMessage(
                invocation_id,
                event,
                event_params,
                headers=self.headers))

        return stream_obj

    async def _on_invocation_message(self, message: InvocationMessage):
        fired_handlers = self.handlers.get(message.target, [])

        if len(fired_handlers) == 0:
            self.logger.info(
                f"Event '{message.target}' hasn't fired any handler")

        for handler in fired_handlers:
            await call_callback(handler, message.arguments)

    async def _on_stream_item_message(self, message: StreamItemMessage):
        fired_handlers = self.stream_handlers.get(
            message.invocation_id, [])

        if len(fired_handlers) == 0:
            self.logger.warning(
                "id '{0}' hasn't fire any stream handler".format(
                    message.invocation_id))

        for handler in fired_handlers:
            await handler.next(message.item)

    async def _on_completion_message(self, message: CompletionMessage):
        fired_handlers = self.stream_handlers.get(
            message.invocation_id, [])

        if message.error is not None and len(message.error) > 0:
            # Stream errors belong to the stream subscription. Only fall
            # back to the connection level handler when the invocation
            # has no stream handler (for example invoke() callbacks).
            stream_handlers = [
                handler for handler in fired_handlers
                if isinstance(handler, AIOStreamHandler)]

            if len(stream_handlers) > 0:
                for handler in stream_handlers:
                    await handler.error(message)
            else:
                await call_callback(self._callbacks.on_error, message)
        else:
            for handler in fired_handlers:
                await handler.complete(message)

        # unregister handler
        if message.invocation_id in self.stream_handlers:
            del self.stream_handlers[message.invocation_id]

    async def _on_stream_invocation_message(
            self, message: StreamInvocationMessage):  # pragma: no cover
        self.logger.debug(f"Stream invocation message {message}")

    async def _on_cancel_invocation_message(
            self, message: CancelInvocationMessage):
        fired_handlers = self.stream_handlers.get(
            message.invocation_id, [])

        if len(fired_handlers) == 0:
            self.logger.warning(
                "id '{0}' hasn't fire any stream handler".format(
                    message.invocation_id))

        for handler in fired_handlers:
            await handler.error(message)

        # unregister handler
        if message.invocation_id in self.stream_handlers:
            del self.stream_handlers[message.invocation_id]

    async def _on_ping_message(self, message: PingMessage):
        self.logger.debug(f"Ping message {message}")

    async def _on_close_message(self, message: CloseMessage):
        self.logger.info(f"Close message received from server {message}")

        if self.transport is not None:
            await self.transport.dispose()

    async def _on_ack_message(self, message: AckMessage):  # pragma: no cover
        self.logger.debug(f"Ack message {message}")

    async def _on_sequence_message(
            self, message: SequenceMessage):  # pragma: no cover
        self.logger.debug(f"Sequence message {message}")

    async def _on_binding_failure(self, message):
        self.logger.error(message)
        await call_callback(self._callbacks.on_error, message)

    async def on_message(self, messages: List[BaseMessage]) -> None:
        for message in messages:
            self.logger.debug(message)

            if message.type == MessageType.invocation_binding_failure:
                await self._on_binding_failure(message)
            elif message.type == MessageType.invocation:
                await self._on_invocation_message(message)
            elif message.type == MessageType.stream_item:
                await self._on_stream_item_message(message)
            elif message.type == MessageType.completion:
                await self._on_completion_message(message)
            elif message.type == MessageType.stream_invocation:
                await self._on_stream_invocation_message(message)
            elif message.type == MessageType.cancel_invocation:
                await self._on_cancel_invocation_message(message)
            elif message.type == MessageType.ping:
                await self._on_ping_message(message)
            elif message.type == MessageType.close:
                await self._on_close_message(message)
                return
            elif message.type == MessageType.ack:  # pragma: no cover
                await self._on_ack_message(message)
            elif message.type == MessageType.sequence:  # pragma: no cover
                await self._on_sequence_message(message)
