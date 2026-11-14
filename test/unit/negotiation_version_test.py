import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from signalrcore.helpers import Helpers
from signalrcore.hub.negotiation import (
    AzureResponse,
    NegotiateResponse,
    NegotiateValidationError,
    NegotiationHandler,
)

POST = "signalrcore.hub.negotiation.RequestHelpers.post"


def transport(transport_name="WebSockets"):
    return {
        "transport": transport_name,
        "transferFormats": ["Text"]
    }


def negotiate_data(version=None, connection_token=None):
    data = {
        "connectionId": "connection-id",
        "availableTransports": [transport()]
    }

    if version is not None:
        data["negotiateVersion"] = version

    if connection_token is not None:
        data["connectionToken"] = connection_token

    return data


class NegotiateResponseVersionTest(unittest.TestCase):
    def test_missing_version_defaults_to_zero(self):
        response = NegotiateResponse.from_dict(negotiate_data())

        self.assertEqual(response.negotiate_version, 0)
        self.assertEqual(response.get_id(), "connection-id")

    def test_version_zero_uses_connection_id(self):
        response = NegotiateResponse.from_dict(negotiate_data(version=0))

        self.assertEqual(response.get_id(), "connection-id")

    def test_version_one_uses_connection_token(self):
        response = NegotiateResponse.from_dict(
            negotiate_data(
                version=1,
                connection_token="connection-token"))

        self.assertEqual(response.negotiate_version, 1)
        self.assertEqual(response.get_id(), "connection-token")

    def test_version_one_does_not_use_access_token(self):
        data = negotiate_data(
            version=1,
            connection_token="connection-token")
        data["accessToken"] = "access-token"

        response = NegotiateResponse.from_dict(data)

        self.assertEqual(response.get_id(), "connection-token")

    def test_version_one_requires_connection_token(self):
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(
                negotiate_data(version=1)))

    def test_boolean_version_is_rejected(self):
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(
                negotiate_data(version=True)))

    def test_non_integer_version_is_rejected(self):
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(
                negotiate_data(version="1")))

    def test_negative_version_is_invalid(self):
        response = NegotiateResponse.from_dict(negotiate_data(version=-1))

        self.assertRaises(ValueError, response.get_id)


class AzureResponseVersionTest(unittest.TestCase):
    def test_access_token_is_used_as_id(self):
        response = AzureResponse.from_dict({
            "url": "https://example.com/negotiate",
            "accessToken": "access-token"
        })

        self.assertEqual(response.get_id(), "access-token")


class NegotiateUrlTest(unittest.TestCase):
    def test_negotiate_version_is_added(self):
        url = Helpers.get_negotiate_url(
            "wss://example.com/chat?foo=bar",
            negotiate_version=1)

        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.path, "/chat/negotiate")
        self.assertEqual(
            parse_qs(parsed.query),
            {"foo": ["bar"], "negotiateVersion": ["1"]})

    def test_trailing_slash_does_not_duplicate_separator(self):
        url = Helpers.get_negotiate_url(
            "ws://example.com/chat/",
            negotiate_version=1)

        self.assertEqual(urlparse(url).path, "/chat/negotiate")

    def test_version_is_not_added_when_omitted(self):
        url = Helpers.get_negotiate_url("ws://example.com/chat")

        self.assertNotIn("negotiateVersion", url)


class NegotiationHandlerTest(unittest.TestCase):
    def build_handler(self, skip_negotiation=False):
        return NegotiationHandler(
            url="wss://example.com/chat",
            headers={"X-Test": "1"},
            proxies={"https": "http://proxy:8080"},
            ssl_context=None,
            skip_negotiation=skip_negotiation)

    @patch(POST)
    def test_negotiate_requests_version_one(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = negotiate_data(
            version=1,
            connection_token="connection-token")
        post.return_value = response

        url, headers, negotiate_response = \
            self.build_handler().negotiate()

        request_url = post.call_args[0][0]
        self.assertEqual(
            parse_qs(urlparse(request_url).query)["negotiateVersion"],
            ["1"])
        self.assertEqual(
            parse_qs(urlparse(url).query)["id"],
            ["connection-token"])
        self.assertEqual(negotiate_response.get_id(), "connection-token")
        self.assertEqual(headers, {
            "X-Test": "1",
            "Content-Type": "application/json"
        })
        self.assertEqual(
            post.call_args.kwargs["proxies"],
            {"https": "http://proxy:8080"})

    @patch(POST)
    def test_negotiate_uses_connection_id_for_version_zero(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = negotiate_data()
        post.return_value = response

        url, _, negotiate_response = self.build_handler().negotiate()

        self.assertEqual(
            parse_qs(urlparse(url).query)["id"],
            ["connection-id"])
        self.assertEqual(negotiate_response.get_id(), "connection-id")

    @patch(POST)
    def test_skip_negotiation_does_not_call_server(self, post):
        url, _, negotiate_response = \
            self.build_handler(skip_negotiation=True).negotiate()

        post.assert_not_called()
        self.assertEqual(url, "wss://example.com/chat")
        self.assertEqual(negotiate_response.negotiate_version, 0)
        self.assertEqual(
            negotiate_response.get_id(),
            negotiate_response.connection_id)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
