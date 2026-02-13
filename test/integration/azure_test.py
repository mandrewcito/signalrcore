import json
import threading
import uuid

from ..base_test_case import BaseTestCase, Urls
from signalrcore.helpers import RequestHelpers
from signalrcore.types import DEFAULT_ENCODING

LOCKS = {}


class TestAzure(BaseTestCase):

    server_url = Urls.azure_func_url_no_ssl

    def test_check_azure_url(self):
        self.assertIsNotNone(self.server_url)

    def test_send(self):
        identifier = str(uuid.uuid4())
        LOCKS[identifier] = threading.Lock()
        LOCKS[identifier].acquire()

        def on_message(args):
            data = args[0]
            name, message, id = (
                data.get("name"),
                data.get("message"),
                data.get("identifier"))
            self.logger.debug(f"{name} {message} {id}")

            if id == identifier:
                LOCKS[identifier].release()

        self.connection.on("newMessage", on_message)

        RequestHelpers.post(
            f"{self.server_url}messages",
            data=json.dumps({
                "sender": "mandrewcito",
                "text": "hello, serverless func!",
                "identifier": identifier}).encode(DEFAULT_ENCODING))

        self.assertTrue(LOCKS[identifier].acquire(timeout=10))

        del LOCKS[identifier]
