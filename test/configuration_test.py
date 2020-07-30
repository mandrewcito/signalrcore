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