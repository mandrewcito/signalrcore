# Request:
# Post negotiate
# GET ENDPOINT with id
# Depending on accept header -> json or bytes

# Response
# !!! can be fragmented into multiple requests !!!

# 204 -> another client with the same id has connected, connection closed
# 200, content-length: 0 -> no data, you can retry
# 400 -> missing ID
# 404 -> No ID on server side (failed negotiation??)

import time
import threading
from typing import Callable, Union
from ...helpers import RequestHelpers, Helpers


class LongPollingBaseClient(object):
    def __init__(
            self,
            thread_name: str,
            url: str,
            connection_id: str = None,
            headers: dict = dict(),
            proxies: dict = dict(),
            verify_ssl: bool = True,
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):

        self.thread_name = thread_name
        self.url = url
        self.connection_id = connection_id
        self.headers = headers
        self.proxies = proxies
        self.verify_ssl = verify_ssl
        self.enable_trace = enable_trace
        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close

        self._thread: threading.Thread = None
        self.logger = Helpers.get_logger()
        self._lock = threading.Lock()
        self._running = False

    def send(self):  # pragma: no cover
        raise NotImplementedError()

    def _recv_frame(self) -> Union[str, bytes, None]:  # pragma: no cover
        raise NotImplementedError()

    def connect(self):
        self._running = True
        self._thread = threading.Thread(
            target=self.run,
            name=self.thread_name)
        self._thread.daemon = True
        self._thread.start()

    def dispose(self):
        is_same_thread = threading.current_thread().name == self.thread_name

        if self._thread and not is_same_thread:
            self._thread.join()
            self._thread = None

    def run(self):
        self.on_open()
        try:
            while self.running:
                message = self._recv_frame()

                if message is not None:
                    self.on_message(self, message)

        except (OSError, Exception) as e:
            self.running = False

            if self.logger:
                self.logger.error(f"Receive error: {e}")

            self.on_error(e)

    def close(self):
        self.logger.debug("Long polling closing connection")
        start = time.time()
        try:
            self._lock.acquire()

            self.is_closing = True
            self._running = False

            # Remove connection from the server
            response = RequestHelpers.delete(
                self.url,
                self.headers,
                self.proxies,
                self.verify_ssl,
                {
                    "id": self.connection_id,
                },
                None)

            status_code,  data = response.status_code, response.json()

            if status_code != 200:
                self.logger.error(
                    f"Error removing connection from the server {data}")

            self.dispose()

            self.on_close()

        except Exception as ex:
            self.logger.error(ex)
        finally:
            self._lock.release()
            self.is_closing = False

        self.logger.debug(
            f"Long polling closed connection {time.time() - start}")


class LongPollingTextClient(LongPollingBaseClient):
    def __init__(self, **kwargs):
        super(LongPollingTextClient, self).__init__(
            "Signalrcore long polling text client",
            **kwargs)


class LongPollingBinaryClient(LongPollingBaseClient):
    def __init__(self, **kwargs):
        super(LongPollingTextClient, self).__init__(
            "Signalrcore long polling binary client",
            **kwargs)
