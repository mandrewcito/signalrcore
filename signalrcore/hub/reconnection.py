from enum import Enum
import threading
import time


class ConnectionStateChecker(threading.Thread):
    def __init__(
            self,
            ping_function,
            keep_alive_interval,
            sleep = 1):
        threading.Thread.__init__(self)
        self.sleep = sleep
        self.keep_alive_interval = keep_alive_interval
        self.last_message = time.time()
        self.ping_function = ping_function
        self.running = True

    def run(self):
        while self.running:
            time.sleep(self.sleep)
            time_without_messages = time.time() - self.last_message
            if self.keep_alive_interval < time_without_messages:
                self.ping_function()


class ReconnectionType(Enum):
    raw=0
    exponential=1


class ReconnectionHandler(object):
    def __init__(
            self,
            sleep_time=5,
            max_attemps=None):
        self.reconnecting = False
        self.max_attemps = max_attemps
        self.sleep_time = sleep_time

class RawReconnectionHandler(ReconnectionHandler):
  pass

class ExponentialReconnectionHandler(ReconnectionHandler):
  pass
