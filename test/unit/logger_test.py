import logging
import unittest

from signalrcore.helpers import Helpers


class ConfigureLoggerTest(unittest.TestCase):
    def setUp(self):
        self.logger = Helpers.get_logger()
        self.handlers = self.logger.handlers[:]
        self.level = self.logger.level
        self.logger.handlers.clear()

    def tearDown(self):
        self.logger.handlers[:] = self.handlers
        self.logger.setLevel(self.level)

    def test_repeated_calls_use_single_handler(self):
        Helpers.configure_logger(logging.INFO)
        Helpers.configure_logger(logging.INFO)

        self.assertEqual(len(self.logger.handlers), 1)

    def test_custom_handler_is_not_duplicated(self):
        handler = logging.StreamHandler()

        Helpers.configure_logger(logging.INFO, handler)
        Helpers.configure_logger(logging.DEBUG, handler)

        self.assertEqual(self.logger.handlers, [handler])

    def test_level_is_updated_on_reused_handler(self):
        Helpers.configure_logger(logging.INFO)
        handler = self.logger.handlers[0]

        Helpers.configure_logger(logging.DEBUG)

        self.assertEqual(self.logger.level, logging.DEBUG)
        self.assertEqual(handler.level, logging.DEBUG)

    def test_formatter_tracks_debug_level(self):
        Helpers.configure_logger(logging.INFO)
        handler = self.logger.handlers[0]

        Helpers.configure_logger(logging.DEBUG)

        self.assertIs(self.logger.handlers[0], handler)
        self.assertIn("%(filename)s", handler.formatter._fmt)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
