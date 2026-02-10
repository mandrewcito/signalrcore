import unittest
import uuid
import sys
import logging
from .base_test_case import Urls


class AIOBaseTestCase(unittest.IsolatedAsyncioTestCase):
    server_url = Urls.server_url_ssl

    def get_random_id(self) -> str:
        return str(uuid.uuid4())

    def is_debug(self) -> bool:
        return "vscode" in sys.argv[0] and "pytest" in sys.argv[0]

    def get_log_level(self):
        return logging.DEBUG\
            if self.is_debug() else logging.ERROR

    def tearDown(self):
        return super().tearDown()

    def setUp(self):
        return super().setUp()
