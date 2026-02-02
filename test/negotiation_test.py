import unittest
from signalrcore.hub.negotiation\
    import NegotiateResponse, NegotiateValidationError


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
                "transport": "patata",
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
