import websocket
import logging
import threading
from signalrcore.hub_connection_builder import HubConnectionBuilder

from test.base_test_case import BaseTestCase, Urls

class TestConfiguration(BaseTestCase):
    
    def test_bad_auth_function(self):
        with self.assertRaises(TypeError):
            self.connection = HubConnectionBuilder()\
                .with_url(self.server_url,
                options={
                    "verify_ssl": False,
                    "access_token_factory": 1234,
                    "headers": {
                        "mycustomheader": "mycustomheadervalue"
                    }
                })

    def test_bad_url(self):
        with self.assertRaises(ValueError):
            self.connection = HubConnectionBuilder()\
                .with_url("")

    def test_bad_options(self):
        with self.assertRaises(TypeError):
            self.connection = HubConnectionBuilder()\
                .with_url(self.server_url,
                options=["ssl", True])
    
    def test_auth_configured(self):
        with self.assertRaises(TypeError):
            hub = HubConnectionBuilder()\
                    .with_url(self.server_url,
                    options={
                        "verify_ssl": False,
                        "headers": {
                            "mycustomheader": "mycustomheadervalue"
                        }
                    })
            hub.has_auth_configured = True
            hub.options["access_token_factory"] = ""
            conn = hub.build()

    def test_enable_trace(self):
        hub = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
            .configure_logging(logging.WARNING, socket_trace=True)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })\
            .build()

        _lock = threading.Lock()
        hub.on_open(lambda: _lock.release())
        _lock.acquire(timeout=self.timeout)
        hub.start()
        _lock.acquire(timeout=self.timeout)
        del _lock

        self.assertTrue(websocket.isEnabledForDebug())
        websocket.enableTrace(False)
        _lock = threading.Lock()
        hub.on_close(lambda: _lock.release())
        _lock.acquire(timeout=self.timeout)
        hub.stop()
        _lock.acquire(timeout=self.timeout)