from test.base_test_case import BaseTestCase
from signalrcore.transport.reconnection\
    import RawReconnectionHandler, IntervalReconnectionHandler


class TestReconnectionHandlerMethods(BaseTestCase):
    def test_raw_handler(self):
        handler = RawReconnectionHandler(5, 10)
        attempt = 0

        while attempt <= 10:
            self.assertEqual(handler.next(), 5)
            attempt = attempt + 1

        self.assertRaises(ValueError, handler.next)

    def test_interval_handler(self):
        intervals = [1, 2, 4, 5, 6]
        handler = IntervalReconnectionHandler(intervals)
        for interval in intervals:
            self.assertEqual(handler.next(), interval)
        self.assertRaises(ValueError, handler.next)

    def tearDown(self):
        pass

    def setUp(self):
        pass
