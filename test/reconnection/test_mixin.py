import threading
import unittest
class TestMixin(unittest.TestCase):
    def reconnect_test(self, connection):
        _lock = threading.Lock()
        
        self.assertTrue(_lock.acquire(timeout=10)) 

        connection.on_open(lambda: _lock.release())

        connection.start()

        self.assertTrue(_lock.acquire(timeout=10)) # Release on Open

        connection.send("DisconnectMe", [])

        self.assertTrue(_lock.acquire(timeout=20)) # released on open
        
        _clock = threading.Lock()
        self.assertTrue(_clock.acquire(timeout=self.timeout))
        connection.on_close(lambda: _clock.release())
        connection.stop()
        self.assertTrue(_clock.acquire(timeout=self.timeout))
        del _clock
        del connection