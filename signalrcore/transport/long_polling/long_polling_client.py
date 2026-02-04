import ssl
import time
import threading

from typing import Callable, Union
from ...helpers import RequestHelpers, Helpers
from ...types import DEFAULT_ENCODING, RECORD_SEPARATOR
from urllib.error import HTTPError
from ..base_client import BaseClient


class LongPollingBaseClient(BaseClient):
    def __init__(
            self,
            thread_name: str,
            url: str,
            receive_header: str,
            connection_id: str = None,
            headers: dict = dict(),
            proxies: dict = dict(),
            ssl_context: ssl.SSLContext = None,
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
        self.ssl_context = ssl_context
        self.enable_trace = enable_trace
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

        self._buffer = b""
        self._byte_separator = RECORD_SEPARATOR.encode(DEFAULT_ENCODING)

    def is_connection_closed(self) -> bool:
        return not self._running\
            or self._thread is None\
            or not self._thread.is_alive()

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

    def dispose(self):
        is_same_thread = threading.current_thread().name == self.thread_name

        if self._thread and not is_same_thread:
            self._thread.join()
            self._thread = None

    def _recv_frame(self) -> Union[str, bytes, None]:
        data = None

        try:
            response = RequestHelpers.get(
                url=Helpers.websocket_to_http(self.url),
                headers=self._receive_headers,
                params={
                    "id": self.connection_id
                },
                timeout=None,
                ssl_context=self.ssl_context
            )

            status_code, data = response.status_code, response.content

            if status_code == 200 or status_code == 204:
                # 204 -> another client with the same
                #   id has connected, connection closed
                # 200, content-length: 0 -> no data, you can retry
                return data

            if status_code == 404 or status_code == 400:
                # 400 -> missing ID
                # 404 -> No ID on server side (failed negotiation??)
                raise OSError(response.content.decode(DEFAULT_ENCODING))
        except TimeoutError:
            return None
        except Exception as err:
            if self.enable_trace:
                self.logger.debug(f"[TRACE] {err}")
        finally:
            if self.enable_trace:
                self.logger.debug(f"[TRACE] {data}")
        return data

    def _append(self, frame: bytes) -> Union[bytes, None]:
        """
            Appends a frame to the current buffer
        Args:
            frame (str, bytes): frame received

        Returns:
            Union[str, bytes, None]: message or messages
                that are complete on the buffer
        """
        self._buffer += frame
        has_record_separator = self._byte_separator in self._buffer

        if not has_record_separator:
            return None

        idx = self._buffer.index(self._byte_separator)
        complete_buffer = self._buffer[0: idx]
        self._buffer = self._buffer[idx + 1:]
        return complete_buffer

    def prepare_data(self, data: bytes) -> Union[bytes, str]:
        return data

    def run(self):
        self.on_open()
        try:
            while self._running:

                frame = self._recv_frame()

                if frame is not None:
                    complete_buffer = self._append(frame)

                    if complete_buffer is not None:
                        message = self.prepare_data(complete_buffer)
                        self.on_message(self, message)

        except (OSError, Exception) as e:
            self._running = False

            if self.logger:
                self.logger.error(f"Receive error: {e}")

            self.on_error(e)

    def close(self):
        if not self._running:
            return

        self.logger.debug("Long polling closing connection")
        start = time.time()
        try:
            self._lock.acquire(timeout=10)

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
        super(LongPollingTextClient, self).__init__(
            "Signalrcore long polling binary client",
            receive_header="binary",
            **kwargs)
