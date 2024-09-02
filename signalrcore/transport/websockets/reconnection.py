import threading
import time
from enum import Enum


class ReconnectionType(Enum):
    raw = 0  # Reconnection with max reconnections and constant sleep time
    interval = 1  # variable sleep time


class ReconnectionHandler(object):
    def __init__(self):
        self.reconnecting = False
        self.attempt_number = 0
        self.last_attempt = time.time()
    
    def can_reconnect(self) -> bool:
        raise NotImplementedError()

    def next(self):
        raise NotImplementedError()

    def reset(self):
        self.attempt_number = 0
        self.reconnecting = False


class RawReconnectionHandler(ReconnectionHandler):
    def __init__(self, sleep_time, max_attempts):
        super(RawReconnectionHandler, self).__init__()
        self.sleep_time = sleep_time
        self.max_reconnection_attempts = max_attempts

    def can_reconnect(self) -> bool:
        return False
    
    def next(self):
        self.reconnecting = True
        if self.max_reconnection_attempts is not None:
            if self.attempt_number <= self.max_reconnection_attempts:
                self.attempt_number += 1
                return self.sleep_time
            else:
                raise ValueError(
                    "Max attemps reached {0}"
                    .format(self.max_reconnection_attempts))
        else:  # Infinite reconnect
            return self.sleep_time


class IntervalReconnectionHandler(ReconnectionHandler):
    def __init__(self, intervals):
        super(IntervalReconnectionHandler, self).__init__()
        self._intervals = intervals
    
    def can_reconnect(self) -> bool:
        return self.attempt_number >= len(self._intervals)

    def next(self):
        self.reconnecting = True
        index = self.attempt_number
        self.attempt_number += 1
        if index >= len(self._intervals):
            raise ValueError(
                "Max intervals reached {0}".format(self._intervals))
        return self._intervals[index]
