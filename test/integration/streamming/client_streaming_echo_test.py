import threading

from signalrcore.subject import Subject
from ...base_test_case import BaseTestCase, Urls


class TestClientStreamEcho(BaseTestCase):
    """Client to server streaming round trip.

    The client uploads a stream (Invocation + streamIds, StreamItem messages
    and a void Completion), the server collects the items and echoes them back
    to the caller, so the client also decodes the server Invocation.
    """

    def test_echo(self):
        items = [str(i) for i in range(5)]
        received = []
        done = threading.Event()

        def on_items(args):
            received.extend(args[0])
            done.set()

        self.connection.on("EchoStreamItems", on_items)

        subject = Subject()
        self.connection.send("EchoStream", subject)

        for item in items:
            subject.next(item)

        subject.complete()

        self.assertTrue(
            done.wait(timeout=10),
            "EchoStreamItems was not received")
        self.assertEqual(received, items)


class TestClientStreamEchoMsgPack(TestClientStreamEcho):
    def get_connection(self):
        return super().get_connection(msgpack=True)


class TestClientNoSslStreamEcho(TestClientStreamEcho):
    server_url = Urls.server_url_no_ssl


class TestClientNoSslStreamEchoMsgPack(TestClientStreamEchoMsgPack):
    server_url = Urls.server_url_no_ssl
