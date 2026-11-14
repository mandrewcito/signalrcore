import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from signalrcore.helpers import RequestHelpers

URLOPEN = "signalrcore.helpers.urllib.request.urlopen"
BUILD_OPENER = "signalrcore.helpers.urllib.request.build_opener"
PROXY_HANDLER = "signalrcore.helpers.urllib.request.ProxyHandler"
HTTPS_HANDLER = "signalrcore.helpers.urllib.request.HTTPSHandler"


class FakeResponse(object):
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self):
        return self.status_code

    def read(self):
        return self.content


class RequestHeadersTest(unittest.TestCase):
    @patch(URLOPEN)
    def test_none_headers_use_json_content_type(self, urlopen):
        urlopen.return_value = FakeResponse(content=b'{"a": 1}')

        response = RequestHelpers.request(
            "https://example.com/negotiate",
            "POST",
            headers=None,
            data=b"abc")

        request = urlopen.call_args[0][0]
        self.assertEqual(
            request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Content-length"), "3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"a": 1})

    @patch(URLOPEN)
    def test_empty_headers_are_not_replaced(self, urlopen):
        urlopen.return_value = FakeResponse()

        RequestHelpers.request(
            "https://example.com/negotiate",
            "GET",
            headers={})

        request = urlopen.call_args[0][0]
        self.assertIsNone(request.get_header("Content-type"))
        self.assertIsNone(request.get_header("Content-length"))

    @patch(URLOPEN)
    def test_headers_are_not_mutated(self, urlopen):
        urlopen.return_value = FakeResponse()
        headers = {"X-Test": "1"}

        RequestHelpers.request(
            "https://example.com/negotiate",
            "POST",
            headers=headers,
            data=b"abc")

        self.assertEqual(headers, {"X-Test": "1"})
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("X-test"), "1")
        self.assertEqual(request.get_header("Content-length"), "3")

    @patch(URLOPEN)
    def test_params_update_querystring(self, urlopen):
        urlopen.return_value = FakeResponse()

        RequestHelpers.request(
            "https://example.com/negotiate?a=1&b=3",
            "GET",
            params={"a": "2"})

        request = urlopen.call_args[0][0]
        query = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(query, {"a": ["2"], "b": ["3"]})


class RequestHandlersTest(unittest.TestCase):
    @patch(URLOPEN)
    @patch(BUILD_OPENER)
    def test_without_handlers_uses_urlopen(self, build_opener, urlopen):
        urlopen.return_value = FakeResponse()

        RequestHelpers.request("https://example.com/negotiate", "GET")

        urlopen.assert_called_once()
        build_opener.assert_not_called()

    @patch(URLOPEN)
    @patch(BUILD_OPENER)
    @patch(PROXY_HANDLER)
    def test_proxies_use_build_opener(
            self, proxy_handler_cls, build_opener, urlopen):
        proxies = {"https": "http://proxy:8080"}
        proxy_handler = Mock()
        proxy_handler_cls.return_value = proxy_handler
        response = FakeResponse()
        opener = Mock()
        opener.open.return_value = response
        build_opener.return_value = opener

        result = RequestHelpers.request(
            "https://example.com/negotiate",
            "GET",
            proxies=proxies)

        proxy_handler_cls.assert_called_once_with(proxies)
        build_opener.assert_called_once_with(proxy_handler)
        opener.open.assert_called_once()
        self.assertEqual(opener.open.call_args.kwargs["timeout"], None)
        urlopen.assert_not_called()
        self.assertEqual(result.status_code, 200)

    @patch(URLOPEN)
    @patch(BUILD_OPENER)
    @patch(HTTPS_HANDLER)
    def test_ssl_context_uses_https_handler(
            self, https_handler_cls, build_opener, urlopen):
        ssl_context = Mock()
        https_handler = Mock()
        https_handler_cls.return_value = https_handler
        opener = Mock()
        opener.open.return_value = FakeResponse()
        build_opener.return_value = opener

        RequestHelpers.request(
            "https://example.com/negotiate",
            "GET",
            ssl_context=ssl_context)

        https_handler_cls.assert_called_once_with(context=ssl_context)
        build_opener.assert_called_once_with(https_handler)
        opener.open.assert_called_once()
        urlopen.assert_not_called()

    @patch(URLOPEN)
    @patch(BUILD_OPENER)
    @patch(HTTPS_HANDLER)
    @patch(PROXY_HANDLER)
    def test_proxies_and_ssl_context_add_both_handlers(
            self,
            proxy_handler_cls,
            https_handler_cls,
            build_opener,
            urlopen):
        proxies = {"https": "http://proxy:8080"}
        ssl_context = Mock()
        proxy_handler = Mock()
        https_handler = Mock()
        proxy_handler_cls.return_value = proxy_handler
        https_handler_cls.return_value = https_handler
        opener = Mock()
        opener.open.return_value = FakeResponse()
        build_opener.return_value = opener

        RequestHelpers.request(
            "https://example.com/negotiate",
            "GET",
            proxies=proxies,
            ssl_context=ssl_context)

        build_opener.assert_called_once_with(
            proxy_handler, https_handler)
        urlopen.assert_not_called()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
