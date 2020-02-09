import uuid
import threading


from .messages.invocation_message import InvocationClientStreamMessage
from .messages.stream_item_message import StreamItemMessage
from .messages.completion_message import CompletionClientStreamMessage


class Subject(object):
    def __init__(self):
        self.connection = None
        self.target = None
        self.invocation_id = str(uuid.uuid4())
        self.lock = threading.RLock()

    def check(self):
        if self.connection is None or self.target is None or self.invocation_id is None:
            raise ValueError(
                "subject must be passed as an agument to a send function. hub_connection.send([method],[subject]")

    def next(self, item):
        self.check()
        with self.lock:
            self.connection.hub.send(StreamItemMessage(
                {},
                self.invocation_id,
                item
            ))

    def start(self):
        self.check()
        with self.lock:
            self.connection.hub.send(InvocationClientStreamMessage(
                {},
                [self.invocation_id],
                self.target,
                []))

    def complete(self):
        self.check()
        with self.lock:
            self.connection.hub.send(CompletionClientStreamMessage(
                {},
                self.invocation_id))
