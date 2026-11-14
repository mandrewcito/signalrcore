import uuid
import threading
from typing import Any
from .messages.invocation_message import InvocationClientStreamMessage
from .messages.stream_item_message import StreamItemMessage
from .messages.completion_message import CompletionClientStreamMessage


class Subject(object):
    """Client to server streaming
    https://docs.microsoft.com/en-gb/aspnet/core/signalr/streaming?view=aspnetcore-5.0#client-to-server-streaming
    items = list(range(0,10))
    subject = Subject()
    connection.send("UploadStream", subject)
    while(len(self.items) > 0):
        subject.next(str(self.items.pop()))
    subject.complete()
    """

    def __init__(self):
        self.connection = None
        self.target = None
        self.invocation_id = str(uuid.uuid4())
        self.lock = threading.Lock()
        self._timeout = 10

    def check(self):
        """Ensures that invocation streaming object is correct

        Raises:
            ValueError: if object is not valid, exception will be raised
        """
        if self.connection is None\
                or self.target is None\
                or self.invocation_id is None:
            raise ValueError(
                "subject must be passed as an argument to a send function. "
                + "hub_connection.send([method],[subject]")

    def _send(self, message):
        """Send a streaming message holding the lock only while sending.

        The lock is always released, even when the transport raises, so a
        failed send does not block every later call on this subject.
        """
        if not self.lock.acquire(timeout=self._timeout):
            raise TimeoutError(
                "Timed out acquiring the stream lock for invocation "
                "{0}".format(self.invocation_id))
        try:
            self.connection.transport.send(message)
        finally:
            self.lock.release()

    def next(self, item: Any):
        """Send next item to the server

        Args:
            item (any): Item that will be streamed
        """
        self.check()
        self._send(StreamItemMessage(
                self.invocation_id,
                item))

    def start(self):
        """Starts streaming
        """
        self.check()
        self._send(InvocationClientStreamMessage(
                    [self.invocation_id],
                    self.target,
                    []))

    def complete(self):
        """Finish streaming
        """
        self.check()
        self._send(CompletionClientStreamMessage(
                self.invocation_id))
