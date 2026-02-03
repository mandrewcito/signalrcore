import socket
import time
import struct
import urllib.parse as parse

from typing import Callable, Union

from ...helpers import Helpers
from ...helpers import RequestHelpers
from ..sockets.base_socket_client import BaseSocketClient, WINDOW_SIZE
from ...types import RECORD_SEPARATOR, DEFAULT_ENCODING

THREAD_NAME = "Signalrcore SSE client"


class SSEClient(BaseSocketClient):
    def __init__(
            self,
            url: str = None,
            connection_id: str = None,
            headers: dict = dict(),
            proxies: dict = dict(),
            verify_ssl: bool = True,
            enable_trace: bool = False,
            on_message: Callable = None,
            on_open: Callable = None,
            on_error: Callable = None,
            on_close: Callable = None):
        super(SSEClient, self).__init__(
            thread_name=THREAD_NAME,
            success_status_code=b"200",
            url=Helpers.websocket_to_http(url),
            connection_id=connection_id,
            is_binary=False,
            headers=headers,
            proxies=proxies,
            verify_ssl=verify_ssl,
            enable_trace=enable_trace,
            on_message=on_message,
            on_open=on_open,
            on_error=on_error,
            on_close=on_close
        )

        self._buffer = b""

    def get_socket_headers(self):
        parsed_url = parse.urlparse(self.url)

        relative_reference = parsed_url.path

        if parsed_url.query:
            relative_reference = f"{parsed_url.path}?{parsed_url.query}"

        return [
            f"GET {relative_reference} HTTP/1.1",
            f"Host: {parsed_url.hostname}",
            "Accept: text/event-stream",
            "Cache-Control: no-cache",
            "Connection: keep-alive"
        ]

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
            verify=self.verify_ssl,
            data=msg_bytes
        )

        status_code, data = response.status_code, response.json()

        self.logger.debug(f"SSE send response: {status_code} - {data}")

    def prepare_data(self, buffer):

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - [prepare data: input] {buffer}")

        array = [x for x in buffer.splitlines() if b'{' in x]
        data = b"".join(array)

        decoded_str = data.decode(DEFAULT_ENCODING)

        if self.is_trace_enabled():
            self.logger.debug(
                f"[TRACE] - [prepare data: output] {decoded_str}")

        return decoded_str\
            .replace("\r\n", "")\
            .replace("data:", "")

    def _recv_frame(self):
        end_record = RECORD_SEPARATOR.encode(DEFAULT_ENCODING)

        while end_record not in self._buffer:
            chunk = self.sock.recv(WINDOW_SIZE)

            if not chunk:
                time.sleep(1)
                continue

            self._buffer += chunk

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] [BUFFER] - {self._buffer}")

        try:
            idx = self._buffer.index(end_record)
            complete_buffer = self._buffer[0: idx]
            self._buffer = self._buffer[idx + 1:]
            return self.prepare_data(complete_buffer)
        except Exception as ex:
            self.logger.debug(ex)
            return ""

    def dispose(self):
        if self.sock is not None:
            try:
                self.sock.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    struct.pack('ii', 1, 0)
                    )
                return super().dispose()
            except Exception as ex:
                self.logger.error(ex)
