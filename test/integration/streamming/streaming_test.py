import time
from ...base_test_case import BaseTestCase, Urls


class TestSendMethod(BaseTestCase):
    server_url = Urls.server_url_ssl
    received = False
    items = list(range(0, 10))
    last_message = time.time()

    def setUp(self):
        self.received = False
        self.items = list(range(0, 10))
        self.last_message = time.time()
        return super().setUp()

    def on_complete(self, x):
        self.complete = True

    def on_next(self, x):
        item = self.items[0]
        self.items = self.items[1:]
        self.assertEqual(x, item)
        self.last_message = time.time()

    def test_stream(self):
        self.complete = False
        self.items = list(range(0, 10))
        self.connection.stream(
            "Counter",
            [len(self.items), 500]).subscribe({
                "next": self.on_next,
                "complete": self.on_complete,
                "error": self.fail  # TestcaseFail
             })

        while not self.complete:
            time.sleep(1)
            self.assertTrue(
                (time.time() - self.last_message) < 5,
                "TIMEOUT")

    def test_stream_error(self):
        self.complete = False
        self.items = list(range(0, 10))

        my_stream = self.connection.stream(
            "Counter",
            [len(self.items), 500])

        self.assertRaises(TypeError, lambda: my_stream.subscribe(None))

        self.assertRaises(
            TypeError,
            lambda: my_stream.subscribe([self.on_next]))

        self.assertRaises(KeyError, lambda: my_stream.subscribe({
                "key": self.on_next
            }))

        self.assertRaises(ValueError, lambda: my_stream.subscribe({
                "next": "",
                "complete": 1,
                "error": []  # TestcaseFail
             }))


class TestSendNoSslMethod(TestSendMethod):
    server_url = Urls.server_url_no_ssl


class TestSendMethodMsgPack(TestSendMethod):
    def get_connection(self):
        return super().get_connection(msgpack=True)


class TestSendMethodNoSslMsgPack(TestSendNoSslMethod):
    def get_connection(self):
        return super().get_connection(msgpack=True)


class TestSseSslStreamMethod(TestSendMethod):
    server_url = Urls.server_url_http_ssl

    def on_next(self, x):
        self.assertTrue(x in self.items)
        self.items.remove(x)
        self.last_message = time.time()

    def get_connection(self, msgpack=False):
        return super().get_connection_sse(
            reconnection=False)

    def test_stream_error(self):
        self.complete = False
        self.items = list(range(0, 10))

        my_stream = self.connection.stream(
            "Counter",
            [len(self.items), 500])

        self.assertRaises(TypeError, lambda: my_stream.subscribe(None))

        self.assertRaises(
            TypeError,
            lambda: my_stream.subscribe([self.on_next]))

        self.assertRaises(KeyError, lambda: my_stream.subscribe({
                "key": self.on_next
            }))

        self.assertRaises(ValueError, lambda: my_stream.subscribe({
                "next": "",
                "complete": 1,
                "error": []  # TestcaseFail
             }))


class TestSseNoSslStreamMethod(TestSseSslStreamMethod):
    server_url = Urls.server_url_http_no_ssl


class TestLongPollingSslStreamMethod(TestSseSslStreamMethod):
    server_url = Urls.server_url_http_ssl

    def get_connection(self, msgpack=False):
        return super().get_connection_long_polling(
            reconnection=False)


class TestLongPollingSslStreamMethod(TestLongPollingSslStreamMethod):
    server_url = Urls.server_url_http_no_ssl
