import asyncio
import uuid
from typing import Any

from ..messages.completion_message import CompletionClientStreamMessage
from ..messages.invocation_message import InvocationClientStreamMessage
from ..messages.stream_item_message import StreamItemMessage


class AIOSubject(object):
    """Asyncio client to server streaming.

    https://docs.microsoft.com/en-gb/aspnet/core/signalr/streaming?view=aspnetcore-5.0#client-to-server-streaming

    Every operation is a coroutine and must be awaited::

        items = list(range(0, 10))
        subject = AIOSubject()
        await connection.send("UploadStream", subject)
        while items:
            await subject.next(str(items.pop()))
        await subject.complete()

    Sends are serialized with an :class:`asyncio.Lock` so concurrent
    produce calls keep the SignalR stream ordering.
    """

    def __init__(self, timeout: float = 10):
        self.connection = None
        self.target = None
        self.invocation_id = str(uuid.uuid4())
        self.lock = asyncio.Lock()
        self._timeout = timeout

    def check(self):
        """Ensures that the streaming object is bound to a connection.

        Raises:
            ValueError: if object is not valid, exception will be raised
        """
        if self.connection is None\
                or self.target is None\
                or self.invocation_id is None:
            raise ValueError(
                "subject must be passed as an argument to a send function. "
                + "hub_connection.send([method],[subject]")

    async def _send(self, message):
        """Sends a streaming message holding the lock only while sending.

        The lock is always released, even when the transport raises, so a
        failed send does not block every later call on this subject.
        """
        try:
            await asyncio.wait_for(
                self.lock.acquire(), timeout=self._timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(
                "Timed out acquiring the stream lock for invocation "
                "{0}".format(self.invocation_id))

        try:
            await self.connection.transport.send(message)
        finally:
            self.lock.release()

    async def next(self, item: Any):
        """Sends the next item to the server.

        Args:
            item (any): Item that will be streamed
        """
        self.check()
        await self._send(StreamItemMessage(
            self.invocation_id,
            item))

    async def start(self):
        """Starts streaming."""
        self.check()
        await self._send(InvocationClientStreamMessage(
            [self.invocation_id],
            self.target,
            []))

    async def complete(self):
        """Finishes streaming."""
        self.check()
        await self._send(CompletionClientStreamMessage(
            self.invocation_id))
