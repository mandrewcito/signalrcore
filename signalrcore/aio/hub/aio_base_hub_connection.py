import uuid
from typing import Any, Awaitable, Callable, List, Optional, Union

from ...hub.base_hub_connection import (
    BaseHubConnection,
    InvocationResult,
)
from ...hub.errors import HubConnectionError
from ...hub.handlers import InvocationHandler, StreamHandler
from ...messages.completion_message import CompletionMessage
from ...messages.invocation_message import InvocationMessage
from ...messages.stream_invocation_message import StreamInvocationMessage
from ...subject import Subject
from ...transport.base_transport import TransportState  # noqa: F401
from ..transport.base_transport import AIOBaseTransport
from .aio_connection_mixin import AIO_CONNECTION_TIMEOUT  # noqa: F401
from .aio_connection_mixin import AIOConnectionMixin


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
            arguments: List[Any],
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
            arguments: Union[List, Subject],
            on_invocation: Optional[Callable[
                [List[CompletionMessage]], Awaitable[None]]] = None,
            invocation_id: Optional[str] = None) -> InvocationResult:
        """Invokes a server function.

        Args:
            method (string): Method name
            arguments (list|Subject): Method parameters
            on_invocation (function, optional): On invocation send callback
                will be raised on send server function ends. It may be a
                plain function or a coroutine function.
            invocation_id (string, optional): Override invocation ID.

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

            await self.transport.send(message)
            result.message = message

        if type(arguments) is Subject:
            arguments.connection = self
            arguments.target = method
            arguments.start()
            result.invocation_id = arguments.invocation_id
            result.message = arguments

        return result

    async def stream(self, event, event_params) -> StreamHandler:
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
        stream_obj = StreamHandler(event, invocation_id)
        self.stream_handlers[invocation_id].append(stream_obj)

        await self.transport.send(
            StreamInvocationMessage(
                invocation_id,
                event,
                event_params,
                headers=self.headers))

        return stream_obj
