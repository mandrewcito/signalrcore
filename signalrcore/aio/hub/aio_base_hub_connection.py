import asyncio
import time
from typing import Awaitable, Any, List, Callable, Optional
from ...hub.base_hub_connection import BaseHubConnection
from ...transport.base_transport import TransportState
from ...messages.completion_message import CompletionMessage

# A start/stop that never reaches the expected state must not block the
# caller forever (for example a handshake rejected by the server).
AIO_CONNECTION_TIMEOUT = 30
POLL_INTERVAL = 0.1


def _state_reached(connection, state: TransportState) -> bool:
    if connection.transport is None:
        # No transport means the connection was never started or was
        # already torn down, which is the disconnected state.
        return state == TransportState.disconnected

    return connection.transport.state == state


async def _wait_for_state(
        connection,
        state: TransportState,
        timeout: float = None) -> None:
    timeout = AIO_CONNECTION_TIMEOUT if timeout is None else timeout
    t0 = time.monotonic()

    while not _state_reached(connection, state):
        remaining = timeout - (time.monotonic() - t0)

        if remaining <= 0:
            raise TimeoutError(f"Timeout waiting for state {state}")

        await asyncio.sleep(min(POLL_INTERVAL, remaining))

    connection.logger.info(
        f"Time elapsed until state change {time.monotonic() - t0}s")


async def _run_and_wait(
        connection,
        action: Callable,
        state: TransportState,
        timeout: float = None):
    thread_task = asyncio.ensure_future(asyncio.to_thread(action))
    state_task = asyncio.ensure_future(
        _wait_for_state(connection, state, timeout))

    try:
        done, _ = await asyncio.wait(
            {thread_task, state_task},
            return_when=asyncio.FIRST_EXCEPTION)

        errors = [
            task.exception()
            for task in done
            if not task.cancelled() and task.exception() is not None
        ]

        if errors:
            raise errors[0]

        return thread_task.result()
    finally:
        # A failed action must not leave the state waiter running.
        if not state_task.done():
            state_task.cancel()


class AIOBaseHubConnection(BaseHubConnection):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def wait_until_state(
            self,
            state: TransportState,
            timeout: float = None) -> Awaitable:
        await _wait_for_state(self, state, timeout)

    async def start(self) -> Awaitable:
        """Starts the connection and waits until the connection
        is ready.

        Returns:
            bool: True if connection stars successfully, False
            if connection cant start or is already connected
        """
        return await _run_and_wait(
            self, super().start, TransportState.connected)

    async def stop(self) -> Awaitable:
        """Stops the connection and waits until the connection
        is closed

        Returns:
            None
        """
        return await _run_and_wait(
            self, super().stop, TransportState.disconnected)

    async def send(
            self,
            method: str,
            arguments: List[Any],
            on_invocation: Optional[Callable[[List[CompletionMessage]], Awaitable[None]]] = None,  # noqa: E501
            invocation_id: str = None) -> Awaitable:
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
        result = await asyncio.to_thread(
            super().invoke,
            method,
            arguments,
            on_invocation,
            invocation_id
        )
        return result

    async def invoke(
            self,
            method: str,
            arguments: List[Any],
            on_invocation: Optional[Callable[[List[CompletionMessage]], Awaitable[None]]] = None,  # noqa: E501
            invocation_id: str = None):
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
        result = await asyncio.to_thread(
            super().invoke,
            method,
            arguments,
            on_invocation,
            invocation_id
        )
        return result

    def on(
            self,
            event: str,
            callback_function: Callable[[List[Any]], None])\
            -> None:
        """Register a callback on the specified event
        Args:
            event (string):  Event name
            callback_function (Function): callback function,
                arguments will be bound
        """
        return super().on(event, callback_function)
