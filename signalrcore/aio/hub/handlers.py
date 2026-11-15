import asyncio
from typing import Callable

from ...helpers import Helpers
from ..utils import call_callback


class AIOStreamHandler(object):
    """Server to client stream subscription with async aware callbacks.

    Items may arrive before ``subscribe`` is called, for example the first
    item of a fast stream. They are buffered and delivered once the
    callbacks are registered so no stream item is lost.
    """

    def __init__(self, event: str, invocation_id: str):
        self.event = event
        self.invocation_id = invocation_id
        self.logger = Helpers.get_logger()
        self.next_callback =\
            lambda _: self.logger.warning(
                "next stream handler fired, no callback configured")
        self.complete_callback =\
            lambda _: self.logger.warning(
                "next complete handler fired, no callback configured")
        self.error_callback =\
            lambda _: self.logger.warning(
                "next error handler fired, no callback configured")
        self._subscribed = False
        self._pending = []
        self._flush_task = None

    def subscribe(self, subscribe_callbacks: dict):
        """Registers the stream callbacks.

        Callbacks may be plain functions or coroutine functions. Events
        received before this call are delivered as soon as the callbacks
        are registered.
        """
        error =\
            " subscribe object must be a dict like {0}"\
            .format({
                "next": None,
                "complete": None,
                "error": None
                })

        if subscribe_callbacks is None or\
                type(subscribe_callbacks) is not dict:
            raise TypeError(error)

        if "next" not in subscribe_callbacks or\
                "complete" not in subscribe_callbacks \
                or "error" not in subscribe_callbacks:
            raise KeyError(error)

        if not callable(subscribe_callbacks["next"])\
                or not callable(subscribe_callbacks["complete"]) \
                or not callable(subscribe_callbacks["error"]):
            raise ValueError("Subscribe callbacks must be functions")

        self.next_callback = subscribe_callbacks["next"]
        self.complete_callback = subscribe_callbacks["complete"]
        self.error_callback = subscribe_callbacks["error"]
        self._subscribed = True

        if self._pending:
            self._flush_task = asyncio.get_running_loop().create_task(
                self._flush())

    async def _call(self, kind: str, value):
        if kind == "next":
            await call_callback(self.next_callback, value)
        elif kind == "complete":
            await call_callback(self.complete_callback, value)
        else:
            await call_callback(self.error_callback, value)

    async def _flush(self):
        while self._pending:
            kind, value = self._pending.pop(0)
            await self._call(kind, value)

    async def _deliver(self, kind: str, value):
        if not self._subscribed:
            self._pending.append((kind, value))
            return

        task = self._flush_task

        if task is not None:
            await task
            self._flush_task = None

        await self._call(kind, value)

    async def next(self, item):
        await self._deliver("next", item)

    async def complete(self, message):
        await self._deliver("complete", message)

    async def error(self, message):
        await self._deliver("error", message)


class AIOInvocationHandler(object):
    """Invocation completion callback with sync and async support."""

    def __init__(self, invocation_id: str, complete_callback: Callable):
        self.invocation_id = invocation_id
        self.complete_callback = complete_callback

    async def complete(self, message):
        await call_callback(self.complete_callback, message)
