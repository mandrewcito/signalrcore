import ssl
import unittest

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.transport.base_transport import BaseTransport
from signalrcore.transport.sockets.utils import create_ssl_context


class SSLContextTest(unittest.TestCase):
    def test_verified_context_requires_tls_1_2(self):
        context = create_ssl_context(True)

        self.assertEqual(
            context.minimum_version,
            ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_unverified_context_requires_tls_1_2(self):
        context = create_ssl_context(False)

        self.assertEqual(
            context.minimum_version,
            ssl.TLSVersion.TLSv1_2)
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)
        self.assertFalse(context.check_hostname)

    def test_builder_default_context_requires_tls_1_2(self):
        builder = HubConnectionBuilder()

        self.assertEqual(
            builder.ssl_context.minimum_version,
            ssl.TLSVersion.TLSv1_2)

    def test_builder_verify_ssl_false_context_requires_tls_1_2(self):
        builder = HubConnectionBuilder().with_url(
            "https://example.com/hub",
            options={"verify_ssl": False})

        self.assertEqual(
            builder.ssl_context.minimum_version,
            ssl.TLSVersion.TLSv1_2)
        self.assertEqual(
            builder.ssl_context.verify_mode,
            ssl.CERT_NONE)

    def test_transport_default_context_requires_tls_1_2(self):
        transport = BaseTransport(url="https://example.com/hub")

        self.assertEqual(
            transport.ssl_context.minimum_version,
            ssl.TLSVersion.TLSv1_2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
