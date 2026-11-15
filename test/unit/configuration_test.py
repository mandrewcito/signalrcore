import ssl
import unittest

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.types import HubProtocolEncoding

from ..base_test_case import Urls


class TestConfiguration(unittest.TestCase):
    server_url = Urls.server_url_ssl

    def test_bad_auth_function(self):
        with self.assertRaises(TypeError):
            self.connection = HubConnectionBuilder()\
                .with_url(
                    self.server_url,
                    options={
                        "verify_ssl": False,
                        "access_token_factory": 1234,
                        "headers": {
                            "mycustomheader": "mycustomheadervalue"
                        }
                    })

    def test_bad_headers(self):
        with self.assertRaises(TypeError):
            self.connection = HubConnectionBuilder()\
                .with_url(
                    self.server_url,
                    options={
                        "verify_ssl": False,
                        "access_token_factory": 1234,
                        "headers": [1, 2]
                    })

    def test_bad_url(self):
        with self.assertRaises(ValueError):
            self.connection = HubConnectionBuilder()\
                .with_url("")

    def test_bad_options(self):
        with self.assertRaises(TypeError):
            self.connection = HubConnectionBuilder()\
                .with_url(
                    self.server_url,
                    options=["ssl", True])

    def test_bad_transport(self):
        with self.assertRaises(TypeError):
            self.connection = HubConnectionBuilder()\
                .with_url(
                    self.server_url,
                    options={
                        "transport": None
                    })

    def test_bad_proxies(self):
        with self.assertRaises(ValueError):
            self.connection = HubConnectionBuilder()\
                .with_url(
                    self.server_url,
                    options={})\
                .configure_proxies({
                    "ff": 22
                })

    def test_proxies(self):
        with self.assertRaises(ValueError):
            self.connection = HubConnectionBuilder()\
                .with_url(
                    self.server_url,
                    options={})\
                .configure_proxies({
                    "http": "192.173.4.5:34"
                })

    def test_bad_protocol(self):
        with self.assertRaises(TypeError):
            self.connection = HubConnectionBuilder()\
                .with_url(
                    self.server_url,
                    options={})\
                .with_hub_protocol({
                    "ff": 22
                })

    def test_protocol(self):
        connection = HubConnectionBuilder()\
            .with_url(
                self.server_url,
                options={})\
            .with_hub_protocol(
                HubProtocolEncoding.binary
            )
        del connection

    def test_auth_configured(self):
        with self.assertRaises(TypeError):
            hub = HubConnectionBuilder()\
                    .with_url(
                        self.server_url,
                        options={
                            "verify_ssl": False,
                            "headers": {
                                "mycustomheader": "mycustomheadervalue"
                            },
                            "access_token_factory": ""
                        })
            _ = hub.build()

    def test_verify_ssl_error(self):
        self.assertRaises(
            TypeError,
            lambda: HubConnectionBuilder()
            .with_url(self.server_url, options={"verify_ssl": 1}))

    def test_verify_ssl_ssl_context_error(self):
        self.assertRaises(
            ValueError,
            lambda: HubConnectionBuilder()
            .with_url(self.server_url, options={
                "verify_ssl": True,
                "ssl_context": ssl.create_default_context()}))

    def test_ssl_context_error(self):
        self.assertRaises(
            TypeError,
            lambda: HubConnectionBuilder()
            .with_url(self.server_url, options={"ssl_context": 1}))
