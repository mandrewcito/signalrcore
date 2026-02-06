import unittest
from urllib.error import URLError
from .base_test_case import BaseTestCase
from signalrcore.hub.negotiation\
    import NegotiateResponse, NegotiateValidationError, \
    AzureResponse
from signalrcore.hub_connection_builder import HubConnectionBuilder


class AzureNegotiationTests(unittest.TestCase):
    def test_invalid_url(self):
        false_obj = {
            "url": 1,
            "accessToken": "asdf"
        }
        self.assertRaises(
            NegotiateValidationError,
            lambda: AzureResponse.from_dict(false_obj)
        )

    def test_invalid_connection_access_token(self):
        false_obj = {
            "negotiateVersion": "https://adsfasdf.org/nego",
            "accessToken": 3
        }
        self.assertRaises(
            NegotiateValidationError,
            lambda: AzureResponse.from_dict(false_obj)
        )

    def test_azure_negotiation(self):
        token = "brand new access token"
        obj = {
            "url": "https://adsfasdf.org/nego",
            "accessToken": token
        }

        data = AzureResponse.from_dict(obj)

        self.assertEqual(
            token,
            data.get_id()
        )


class NegotiationTests(unittest.TestCase):

    def test_data_object(self):
        false_obj = [1, 3]
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(false_obj)
        )

    def test_invalid_version(self):
        false_obj = {
            "negotiateVersion": "f"
        }
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(false_obj)
        )

    def test_invalid_connection_id(self):
        false_obj = {
            "negotiateVersion": 1,
            "connectionId": None
        }
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(false_obj)
        )

    def test_invalid_available_transports(self):
        false_obj = {
            "negotiateVersion": 0,
            "connectionId": "ff",
            "availableTransports": 2
        }
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(false_obj)
        )

    def test_invalid_available_transport_object(self):
        false_obj = {
            "negotiateVersion": 0,
            "connectionId": "12",
            "availableTransports": [3]
        }
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(false_obj)
        )

    def test_invalid_available_transport_name(self):
        false_obj = {
            "negotiateVersion": 0,
            "connectionId": "12",
            "availableTransports": [{
                "transport": "foo",
                "transferFormats": "f"
            }]
        }
        self.assertRaises(
            ValueError,
            lambda: NegotiateResponse.from_dict(false_obj)
        )

    def test_invalid_available_transfer_format(self):
        false_obj = {
            "negotiateVersion": 0,
            "connectionId": "12",
            "availableTransports": [{
                "transport": "WebSockets",
                "transferFormats": "f"
            }]
        }
        self.assertRaises(
            NegotiateValidationError,
            lambda: NegotiateResponse.from_dict(false_obj)
        )

    def test_valid_object(self):
        false_obj = {
            "negotiateVersion": 0,
            "connectionId": "12",
            "availableTransports": [{
                "transport": "WebSockets",
                "transferFormats": ["Text"]
            }]
        }

        data = NegotiateResponse.from_dict(false_obj)

        self.assertEqual(
            "12",
            data.get_id())

        self.assertEqual(
            0,
            data.negotiate_version
        )

    def test_get_id(self):
        token = "asdf"
        false_obj = {
            "negotiateVersion": 1,
            "accessToken": token,
            "connectionId": "12",
            "availableTransports": [{
                "transport": "WebSockets",
                "transferFormats": ["Text"]
            }]
        }

        data = NegotiateResponse.from_dict(false_obj)

        self.assertEqual(
            token,
            data.get_id())


class NegotiationErrorTest(BaseTestCase):
    def tearDown(self):  # pragma: no cover
        pass

    def setUp(self):  # pragma: no cover
        pass

    def test_invalid_url(self):
        builder = HubConnectionBuilder()\
            .with_url(
                "https://randomurl.org/",
                options={
                    "verify_ssl": False}
                )\
            .configure_logging(
                self.get_log_level(),
                socket_trace=self.is_debug())\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })

        hub = builder.build()

        self.assertRaises(
            URLError,
            hub.start)
