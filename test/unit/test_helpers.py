import json
import ssl
import unittest
from unittest.mock import patch, MagicMock

from signalrcore.helpers import RequestHelpers, HTTPResponse
from signalrcore.aio.aio_helpers import AIORequestHelpers, AIOHTTPResponse
from signalrcore.types import DEFAULT_ENCODING


class TestHTTPResponse(unittest.TestCase):
    def test_constructs_and_reads_status_code_and_content(self):
        response = HTTPResponse(None, None, MagicMock(
            getcode=lambda: 200, read=lambda: b'{"key": "value"}'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"key": "value"}')

    def test_json_parses_non_empty_body(self):
        response = HTTPResponse(None, None, MagicMock(
            getcode=lambda: 200, read=lambda: b'{"key": "value"}'))
        self.assertEqual(response.json(), {"key": "value"})

    def test_json_returns_none_for_empty_body(self):
        response = HTTPResponse(None, None, MagicMock(
            getcode=lambda: 200, read=lambda: b''))
        self.assertIsNone(response.json())


class TestAIOHTTPResponse(unittest.TestCase):
    def test_constructs_and_reads_status_code_and_content(self):
        response = AIOHTTPResponse(200, b'{"key": "value"}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'{"key": "value"}')

    def test_json_parses_non_empty_body(self):
        response = AIOHTTPResponse(200, b'{"key": "value"}')
        self.assertEqual(response.json(), {"key": "value"})

    def test_json_returns_none_for_empty_body(self):
        response = AIOHTTPResponse(200, b'')
        self.assertIsNone(response.json())


class TestRequestHelpersUpdateQuerystring(unittest.TestCase):
    def test_no_params_returns_url_unchanged(self):
        url = "http://example.com/path"
        result = RequestHelpers.update_querystring(url)
        self.assertEqual(result, url)

    def test_with_params_appends_query_string(self):
        url = "http://example.com/path"
        result = RequestHelpers.update_querystring(url, {"key": "value"})
        self.assertEqual(result, "http://example.com/path?key=value")

    def test_existing_params_are_preserved_and_new_ones_appended(self):
        url = "http://example.com/path?a=1"
        result = RequestHelpers.update_querystring(url, {"b": "2"})
        self.assertIn("a=1", result)
        self.assertIn("b=2", result)

    def test_existing_param_is_overwritten(self):
        url = "http://example.com/path?a=1"
        result = RequestHelpers.update_querystring(url, {"a": "2"})
        self.assertEqual(result, "http://example.com/path?a=2")


class TestRequestHelpersHttpMethods(unittest.TestCase):
    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_get_returns_http_response(self, mock_request, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'{"key": "value"}'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        result = RequestHelpers.get("http://example.com")

        self.assertIsInstance(result, HTTPResponse)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"key": "value"})

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_post_returns_http_response(self, mock_request, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 201
        mock_response.read.return_value = b'created'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        result = RequestHelpers.post("http://example.com")

        self.assertIsInstance(result, HTTPResponse)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.content, b'created')

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_post_with_data_sends_content_length(
            self, mock_request, mock_urlopen):
        data = b'{"hello": "world"}'
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'ok'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        RequestHelpers.post("http://example.com", data=data)

        _, kwargs = mock_request.call_args
        self.assertIn("Content-Length", kwargs["headers"])
        self.assertEqual(
            kwargs["headers"]["Content-Length"], str(len(data)))
        self.assertEqual(kwargs["data"], data)

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_delete_returns_http_response(self, mock_request, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 204
        mock_response.read.return_value = b''
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        result = RequestHelpers.delete("http://example.com")

        self.assertIsInstance(result, HTTPResponse)
        self.assertEqual(result.status_code, 204)

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_request_passes_custom_headers(
            self, mock_request, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'ok'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        RequestHelpers.request(
            "http://example.com", "GET",
            headers={"Authorization": "Bearer token"})

        _, kwargs = mock_request.call_args
        self.assertEqual(
            kwargs["headers"]["Authorization"], "Bearer token")

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_request_passes_timeout(self, mock_request, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'ok'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        RequestHelpers.request(
            "http://example.com", "GET", timeout=5.0)

        mock_urlopen.assert_called_once()
        _, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs["timeout"], 5.0)

    @patch("urllib.request.build_opener")
    @patch("urllib.request.ProxyHandler")
    @patch("urllib.request.Request")
    def test_request_with_proxies_uses_build_opener(
            self, mock_request, mock_proxy_handler, mock_build_opener):
        mock_opener = MagicMock()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'ok'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_opener.return_value = mock_cm
        mock_build_opener.return_value = mock_opener

        RequestHelpers.request(
            "http://example.com", "GET",
            proxies={"http": "http://proxy:8080"})

        mock_proxy_handler.assert_called_once_with(
            {"http": "http://proxy:8080"})
        mock_build_opener.assert_called_once()

    @patch("urllib.request.urlopen")
    @patch("urllib.request.Request")
    def test_request_with_ssl_context_passes_it_to_urlopen(
            self, mock_request, mock_urlopen):
        ctx = ssl.create_default_context()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'ok'
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_cm

        RequestHelpers.request(
            "http://example.com", "GET", ssl_context=ctx)

        _, kwargs = mock_urlopen.call_args
        self.assertIs(kwargs["context"], ctx)


class TestAIORequestHelpersUpdateQuerystring(unittest.TestCase):
    def test_matches_sync_behavior(self):
        url = "http://example.com/path?a=1"
        result = AIORequestHelpers.update_querystring(url, {"b": "2"})
        expected = RequestHelpers.update_querystring(url, {"b": "2"})
        self.assertEqual(result, expected)


class TestAIORequestHelpersHttpMethods(unittest.IsolatedAsyncioTestCase):
    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_get_returns_aio_http_response(self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(
            200, b'{"key": "value"}')

        result = await AIORequestHelpers.get("http://example.com")

        self.assertIsInstance(result, AIOHTTPResponse)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"key": "value"})

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_get_passes_correct_args(self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(200, b'')

        await AIORequestHelpers.get("http://example.com")

        args, _ = mock_execute.call_args
        self.assertIn("http://example.com", args)
        self.assertIn("GET", args)

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_post_returns_aio_http_response(self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(
            201, b'created')

        result = await AIORequestHelpers.post("http://example.com")

        self.assertIsInstance(result, AIOHTTPResponse)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.content, b'created')

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_post_with_data_sends_content_length(
            self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(200, b'ok')
        data = b'{"hello": "world"}'

        await AIORequestHelpers.post(
            "http://example.com", data=data)

        args, _ = mock_execute.call_args
        self.assertIn("POST", args)
        self.assertIn(b'{"hello": "world"}', args)

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_delete_returns_aio_http_response(self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(204, b'')

        result = await AIORequestHelpers.delete("http://example.com")

        self.assertIsInstance(result, AIOHTTPResponse)
        self.assertEqual(result.status_code, 204)

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_request_passes_custom_headers(
            self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(200, b'ok')

        await AIORequestHelpers.request(
            "http://example.com", "GET",
            headers={"Authorization": "Bearer token"})

        args, _ = mock_execute.call_args
        url, method, headers = args[0], args[1], args[2]
        self.assertEqual(method, "GET")
        self.assertEqual(
            headers["Authorization"], "Bearer token")

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_request_passes_proxies(self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(200, b'ok')

        await AIORequestHelpers.request(
            "http://example.com", "GET",
            proxies={"http": "http://proxy:8080"})

        args, _ = mock_execute.call_args
        proxy_handler = args[4]
        self.assertIsNotNone(proxy_handler)

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_request_passes_timeout(self, mock_execute):
        mock_execute.return_value = AIOHTTPResponse(200, b'ok')

        await AIORequestHelpers.request(
            "http://example.com", "GET", timeout=5.0)

        args, _ = mock_execute.call_args
        timeout = args[6]
        self.assertEqual(timeout, 5.0)

    @patch("signalrcore.aio.aio_helpers._execute_request")
    async def test_request_passes_ssl_context(self, mock_execute):
        ctx = ssl.create_default_context()
        mock_execute.return_value = AIOHTTPResponse(200, b'ok')

        await AIORequestHelpers.request(
            "http://example.com", "GET", ssl_context=ctx)

        args, _ = mock_execute.call_args
        ssl_context = args[5]
        self.assertIs(ssl_context, ctx)
