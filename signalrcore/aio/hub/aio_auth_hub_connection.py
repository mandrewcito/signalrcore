import asyncio
import time
from .aio_base_hub_connection import TransportState
from ...hub.auth_hub_connection import AuthHubConnection
from typing import Awaitable, List, Callable, Optional, Any
from ...messages.completion_message import CompletionMessage


class AIOAuthHubConnection(AuthHubConnection):
    def __init__(self, **kwargs):
        super(AIOAuthHubConnection, self).__init__(**kwargs)

    async def wait_until_state(
            self,
            state: TransportState,
            timeout: float = None) -> Awaitable:
        t0 = time.time()
        while self.transport is None or self.transport.state != state:
            await asyncio.sleep(0.1)
            if timeout is not None and t0 + timeout < time.time():  # pragma: no cover # noqa E501
                raise TimeoutError()
        self.logger.info(
            f"Time elapsed until state change {time.time() - t0}s")

    async def start(self) -> Awaitable:
        t1 = asyncio.to_thread(super().start)
        t2 = self.wait_until_state(TransportState.connected)

        result, _ = await asyncio.gather(t1, t2)

        return result

    async def stop(self) -> Awaitable:
        t1 = asyncio.to_thread(super().stop)
        t2 = self.wait_until_state(TransportState.disconnected)
        result, _ = await asyncio.gather(t1, t2)
        return result

    async def send(
            self,
            method: str,
            arguments: List[Any],
            on_invocation: Optional[Callable[[List[CompletionMessage]], Awaitable[None]]] = None,  # noqa: E501
            invocation_id: str = None) -> Awaitable:

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
            callback_function: Callable[[List[Any]], Awaitable[None]])\
            -> None:
        return super().on(event, callback_function)
