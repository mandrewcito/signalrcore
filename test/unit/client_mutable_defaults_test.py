import unittest

from signalrcore.hub.base_hub_connection import BaseHubConnection
from signalrcore.transport.long_polling.long_polling_client import \
    LongPollingTextClient
from signalrcore.transport.sse.sse_client import SSEClient
from signalrcore.transport.websockets.websocket_client import WebSocketClient

FACTORIES = (
    lambda: WebSocketClient(url="ws://localhost/chat"),
    lambda: LongPollingTextClient(url="http://localhost/chat"),
    lambda: SSEClient(url="http://localhost/chat"),
    lambda: BaseHubConnection(url="http://localhost/chat"),
)


class MutableDefaultArgumentsTest(unittest.TestCase):
    def test_headers_are_not_shared_between_instances(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory):
                first = factory()
                second = factory()

                first.headers["x-test"] = "value"

                self.assertNotIn("x-test", second.headers)

    def test_proxies_are_not_shared_between_instances(self):
        for factory in FACTORIES:
            with self.subTest(factory=factory):
                first = factory()
                second = factory()

                first.proxies["http"] = "http://proxy:8080"

                self.assertNotIn("http", second.proxies)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
