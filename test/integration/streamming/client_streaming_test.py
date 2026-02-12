from signalrcore.subject import Subject
from ...base_test_case import BaseTestCase, Urls


class TestClientStreamMethod(BaseTestCase):

    def test_stream(self):
        self.complete = False
        items = list(range(0, 10))
        subject = Subject()
        self.connection.send("UploadStream", subject)

        while (len(items) > 0):
            subject.next(str(items.pop()))

        subject.complete()

        self.assertTrue(len(items) == 0)


class TestClientStreamMethodMsgPack(TestClientStreamMethod):
    def get_connection(self):
        return super().get_connection(msgpack=True)


class TestClientNoSslStreamMethodMsgPack(TestClientStreamMethodMsgPack):
    server_url = Urls.server_url_no_ssl


class TestClientNoSslStreamMethod(TestClientStreamMethod):
    server_url = Urls.server_url_no_ssl


class TestClientSseSslStreamMethod(TestClientStreamMethod):
    server_url = Urls.server_url_http_ssl

    def get_connection(self, msgpack=False):
        return super().get_connection_sse(
            reconnection=False)


class TestClientSseNoSslStreamMethod(TestClientSseSslStreamMethod):
    server_url = Urls.server_url_http_no_ssl


class TestClientLongPollingSslStreamMethod(TestClientStreamMethod):
    server_url = Urls.server_url_http_ssl

    def get_connection(self, msgpack=False):
        return super().get_connection_long_polling(
            reconnection=False)


class TestClientLongPollingNoSslStreamMethod(
        TestClientLongPollingSslStreamMethod):
    server_url = Urls.server_url_http_no_ssl
