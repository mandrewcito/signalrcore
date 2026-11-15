from typing import Callable

from ...helpers import Helpers
from ..utils import call_callback


class AIOStreamHandler(object):
    """Server to client stream subscription with async aware callbacks."""

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

    def subscribe(self, subscribe_callbacks: dict):
        """Registers the stream callbacks.

        Callbacks may be plain functions or coroutine functions.
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

    async def next(self, item):
        await call_callback(self.next_callback, item)

    async def complete(self, message):
        await call_callback(self.complete_callback, message)

    async def error(self, message):
        await call_callback(self.error_callback, message)


class AIOInvocationHandler(object):
    """Invocation completion callback with sync and async support."""

    def __init__(self, invocation_id: str, complete_callback: Callable):
        self.invocation_id = invocation_id
        self.complete_callback = complete_callback

    async def complete(self, message):
        await call_callback(self.complete_callback, message)
