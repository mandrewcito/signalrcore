from ..base_test_case import BaseTestCase
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol
from signalrcore.types import HttpTransportType

LOCKS = {}


class TestTraceEnable(BaseTestCase):
    def get_connection(self):
        log_level = self.get_log_level()

        options = {"verify_ssl": False}

        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options=options)\
            .configure_logging(log_level, socket_trace=True)

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def test_trace(self):
        self.assertTrue(self.connection.transport.is_trace_enabled())


class TraceEnableMsgPackTest(BaseTestCase):
    def get_connection(self):
        log_level = self.get_log_level()

        options = {"verify_ssl": False}

        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options=options)\
            .configure_logging(log_level, socket_trace=True)

        builder.with_hub_protocol(MessagePackHubProtocol())

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def test_trace(self):
        self.assertTrue(self.connection.transport.is_trace_enabled())


class TraceEnableSsePackTest(BaseTestCase):
    def get_connection(self, msgpack=False, options=None):
        log_level = self.get_log_level()

        options = {
            "verify_ssl": False,
            "transport": HttpTransportType.server_sent_events
        }

        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options=options)\
            .configure_logging(log_level, socket_trace=True)

        if msgpack:
            builder.with_hub_protocol(MessagePackHubProtocol())

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def test_trace(self):
        self.assertTrue(self.connection.transport.is_trace_enabled())


class TraceEnableLongPollingTest(BaseTestCase):
    def get_connection(self):
        log_level = self.get_log_level()

        options = {
            "verify_ssl": False,
            "transport": HttpTransportType.long_polling
        }

        builder = HubConnectionBuilder()\
            .with_url(self.server_url, options=options)\
            .configure_logging(log_level, socket_trace=True)

        hub = builder.build()
        hub.on_open(self.on_open)
        hub.on_close(self.on_close)
        return hub

    def test_trace(self):
        self.assertTrue(self.connection.transport.is_trace_enabled())
