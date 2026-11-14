import threading
import unittest

from signalrcore.transport.reconnection import\
    ConnectionStateChecker, THREAD_NAME


class ConnectionStateCheckerTest(unittest.TestCase):
    def setUp(self):
        self.checker = ConnectionStateChecker(
            lambda: None,
            keep_alive_interval=1000)

    def tearDown(self):
        self.checker.stop()

    def test_start_uses_checker_thread_name(self):
        self.checker.start()

        self.assertEqual(self.checker._thread.name, THREAD_NAME)

    def test_double_start_does_not_block(self):
        self.checker.start()

        worker = threading.Thread(target=self.checker.start)
        worker.start()
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())

    def test_restart_after_stop_creates_new_thread(self):
        self.checker.start()
        first_thread = self.checker._thread
        self.checker.stop()

        self.checker.start()

        self.assertIsNotNone(self.checker._thread)
        self.assertIsNot(self.checker._thread, first_thread)
        self.assertTrue(self.checker._thread.is_alive())

    def test_dead_thread_is_recreated(self):
        dead_thread = threading.Thread(target=lambda: None)
        dead_thread.start()
        dead_thread.join()
        self.checker._thread = dead_thread

        self.checker.start()

        self.assertTrue(self.checker._thread.is_alive())

    def test_stop_from_checker_thread_does_not_deadlock(self):
        stopped = threading.Event()

        def ping():
            self.checker.stop()
            stopped.set()

        self.checker.ping_function = ping
        self.checker.keep_alive_interval = -1
        self.checker.sleep = 0
        self.checker.start()

        self.assertTrue(stopped.wait(timeout=2))
        self.assertFalse(self.checker.running)
        self.assertIsNone(self.checker._thread)

    def test_ping_exception_does_not_kill_the_thread(self):
        calls = []
        stop = threading.Event()

        def ping():
            calls.append(1)
            if len(calls) < 2:
                raise OSError("ping failed")
            stop.set()
            self.checker.stop()

        self.checker.ping_function = ping
        self.checker.keep_alive_interval = -1
        self.checker.sleep = 0
        self.checker.start()

        self.assertTrue(stop.wait(timeout=2))
        self.assertGreaterEqual(len(calls), 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
