import ssl
import time
import threading

from typing import Callable, List, Union
from ...helpers import RequestHelpers, Helpers
from ...types import DEFAULT_ENCODING, RECORD_SEPARATOR
from urllib.error import HTTPError
from ..base_client import BaseClient

# The server holds long polling requests for up to ~90 seconds, so the
# client timeout must be slightly higher to let the poll finish. A finite
# timeout is required: with timeout=None a dead connection blocks the
# receive thread forever and stop() can never join it.
REQUEST_TIMEOUT = 100
DISPOSE_JOIN_TIMEOUT = 5


class LongPollingBaseClient(BaseClient):
    def __init__(
            self,
            thread_name: str,
            url: str,
            receive_header: str,
            connection_id: str = None,
            headers: Union[dict, None] = None,
            proxies: Union[dict, None] = None,
            ssl_context: ssl.SSLContext = None,
            enable_trace: bool = False,
            timeout: float = REQUEST_TIMEOUT,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):

        self.thread_name = thread_name
        self.url = url
        self.connection_id = connection_id
        self.headers = headers if headers is not None else {}
        self.proxies = proxies if proxies is not None else {}
        self.ssl_context = ssl_context
        self.enable_trace = enable_trace
        self.timeout = timeout
        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close
        self._receive_headers = {
            "Accept": receive_header
        }

        self._thread: threading.Thread = None
        self.logger = Helpers.get_logger()
        self._lock = threading.Lock()
        self._running = False
        self.is_closing = False

        self._buffer = b""
        self._byte_separator = RECORD_SEPARATOR.encode(DEFAULT_ENCODING)

    def is_connection_closed(self) -> bool:
        return not self._running\
            or self._thread is None\
            or not self._thread.is_alive()

    def is_trace_enabled(self):
        return self.enable_trace

    def send(
            self,
            message: Union[str, bytes],
            headers: dict = None):

        headers = {
            "Content-Type": "application/octet-stream",
        } if headers is None else headers

        headers.update(self.headers)

        msg_bytes =\
            message\
            if type(message) is bytes else\
            message.encode(DEFAULT_ENCODING)

        response = RequestHelpers.post(
            Helpers.websocket_to_http(self.url),
            headers=headers,
            proxies=self.proxies,
            data=msg_bytes,
            timeout=self.timeout,
            ssl_context=self.ssl_context
        )

        status_code, data = response.status_code, response.json()

        self.logger.debug(
            f"Long Polling send response: {status_code} - {data}")

    def connect(self):
        self._running = True
        self._thread = threading.Thread(
            target=self.run,
            name=self.thread_name)
        self._thread.daemon = True
        self._thread.start()

    def dispose(self, timeout: float = DISPOSE_JOIN_TIMEOUT):
        # Stop the receive loop before joining, otherwise a healthy
        # long polling connection would block the join until the next
        # message arrives.
        self._running = False

        thread = self._thread
        is_same_thread = threading.current_thread().name == self.thread_name

        if thread and not is_same_thread:
            thread.join(timeout=timeout)

            if thread.is_alive():
                # The request is still in flight. It will end when the
                # request timeout expires; do not block the caller.
                self.logger.warning(
                    "Long polling receive thread did not stop in time")
                return

            self._thread = None

    def _recv_frame(self) -> Union[str, bytes, None]:
        try:
            response = RequestHelpers.get(
                url=Helpers.websocket_to_http(self.url),
                headers=self._receive_headers,
                params={
                    "id": self.connection_id
                },
                timeout=self.timeout,
                ssl_context=self.ssl_context
            )
        except HTTPError as err:
            # urlopen raises HTTPError on 4xx/5xx, before a response
            # is available.
            # 400 -> missing ID
            # 404 -> No ID on server side (failed negotiation??)
            if err.code in (400, 404):
                raise OSError(
                    f"Connection closed by server ({err.code})") from err
            raise
        except TimeoutError:
            return None

        status_code, data = response.status_code, response.content

        if status_code == 204:
            # another client with the same id has connected,
            # connection closed
            raise OSError("Connection closed by server (204)")

        if status_code != 200:
            raise OSError(
                f"Unexpected long polling status {status_code}")

        # 200, content-length: 0 -> no data, you can retry
        if self.enable_trace:
            self.logger.debug(f"[TRACE] {data}")

        return data

    def _append(self, frame: bytes) -> List[bytes]:
        """
            Appends a frame to the current buffer
        Args:
            frame (str, bytes): frame received

        Returns:
            List[bytes]: all messages that are complete on the buffer
        """
        self._buffer += frame
        complete_buffers = []

        while self._byte_separator in self._buffer:
            idx = self._buffer.index(self._byte_separator)
            complete_buffers.append(self._buffer[0: idx])
            self._buffer = self._buffer[idx + 1:]

        return complete_buffers

    def prepare_data(self, data: bytes) -> Union[bytes, str]:
        return data

    def run(self):
        try:
            self.on_open()

            while self._running:

                frame = self._recv_frame()

                if frame is not None:
                    for complete_buffer in self._append(frame):
                        if not complete_buffer:
                            continue

                        message = self.prepare_data(complete_buffer)
                        self.on_message(self, message)

        except Exception as e:
            self._running = False

            if self.logger:
                self.logger.error(f"Receive error: {e}")

            # OSError and subclasses (HTTPError, URLError,
            # ConnectionResetError...) mean the connection is gone.
            if isinstance(e, OSError):
                self.on_close()
            else:
                self.on_error(e)

    def close(self):
        if not self._running:
            return

        self.logger.debug("Long polling closing connection")
        start = time.time()

        if not self._lock.acquire(timeout=10):
            self.logger.warning(
                "Long polling close already in progress")
            return

        try:
            self.is_closing = True
            self._running = False

            # Remove connection from the server
            response = RequestHelpers.delete(
                Helpers.websocket_to_http(self.url),
                self.headers,
                self.proxies,
                {
                    "id": self.connection_id,
                },
                None,
                timeout=self.timeout,
                ssl_context=self.ssl_context)

            status_code,  data = response.status_code, response.json()

            if status_code not in [200, 202]:
                self.logger.error(
                    f"Error removing connection from the server {data}")

            self.dispose()
        except HTTPError as ex:
            if ex.status != 404:
                self.logger.error(ex)
        except Exception as ex:
            self.logger.error(ex)
        finally:
            self._lock.release()
            self.is_closing = False
            self.on_close()

        self.logger.debug(
            f"Long polling closed connection {time.time() - start}")


class LongPollingTextClient(LongPollingBaseClient):
    def __init__(self, **kwargs):
        super(LongPollingTextClient, self).__init__(
            "Signalrcore long polling text client",
            receive_header="Text",
            **kwargs)

    def prepare_data(self, data):
        return data.decode(DEFAULT_ENCODING)


class LongPollingBinaryClient(LongPollingBaseClient):
    def __init__(self, **kwargs):
        super(LongPollingBinaryClient, self).__init__(
            "Signalrcore long polling binary client",
            receive_header="binary",
            **kwargs)
