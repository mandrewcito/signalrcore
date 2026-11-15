import unittest

from signalrcore.hub.base_hub_connection import BaseHubConnection
from signalrcore.hub.handlers import InvocationHandler, StreamHandler
from signalrcore.messages.completion_message import CompletionMessage


class CompletionMessageCallbacksTest(unittest.TestCase):
    def setUp(self):
        self.connection = BaseHubConnection(url="http://localhost/hub")
        self.events = []

    def add_stream_handler(self):
        handler = StreamHandler("Counter", "invocation-id")
        handler.subscribe({
            "next": lambda item: self.events.append(("next", item)),
            "complete": lambda message: self.events.append(
                ("complete", message)),
            "error": lambda message: self.events.append(("error", message)),
        })
        self.connection.stream_handlers["invocation-id"].append(handler)
        return handler

    def test_stream_error_fires_stream_error_callback(self):
        self.add_stream_handler()
        self.connection.on_error(
            lambda message: self.events.append(("global_error", message)))

        message = CompletionMessage("invocation-id", None, "boom")
        self.connection.on_message([message])

        self.assertEqual(self.events, [("error", message)])
        self.assertNotIn("invocation-id", self.connection.stream_handlers)

    def test_stream_completion_fires_complete_callback(self):
        self.add_stream_handler()

        message = CompletionMessage("invocation-id", None, None)
        self.connection.on_message([message])

        self.assertEqual(self.events, [("complete", message)])
        self.assertNotIn("invocation-id", self.connection.stream_handlers)

    def test_invocation_error_falls_back_to_global_error_callback(self):
        self.connection.stream_handlers["invocation-id"].append(
            InvocationHandler(
                "invocation-id",
                lambda message: self.events.append(("invoke", message))))
        self.connection.on_error(
            lambda message: self.events.append(("global_error", message)))

        message = CompletionMessage("invocation-id", None, "boom")
        self.connection.on_message([message])

        self.assertEqual(self.events, [("global_error", message)])
        self.assertNotIn("invocation-id", self.connection.stream_handlers)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
