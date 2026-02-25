import socket
import ssl
import struct
import threading
import urllib.parse as parse

from typing import Callable, Union

from ...helpers import Helpers
from ...helpers import RequestHelpers
from ..sockets.base_socket_client import BaseSocketClient, WINDOW_SIZE
from ..sockets.errors import SocketClosedError, SocketHandshakeError
from ...types import RECORD_SEPARATOR, DEFAULT_ENCODING, CRLF, CRLF_CRLF

THREAD_NAME = "Signalrcore SSE client"


def parse_sse_to_json(raw: bytes) -> dict:
    text = raw.decode(DEFAULT_ENCODING, errors='replace')

    start = text.find('{')
    if start == -1:  # pragma: no cover
        raise ValueError("JSON not found in content")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:  # pragma: no cover
            escape_next = False
            continue

        if char == '\\' and in_string:  # pragma: no cover
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    raise ValueError(f"Malformed json {raw}")  # pragma: no cover


class SSEClient(BaseSocketClient):
    def __init__(
            self,
            url: str = None,
            connection_id: str = None,
            headers: dict = dict(),
            proxies: dict = dict(),
            ssl_context: ssl.SSLContext = None,
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
            ssl_context=ssl_context,
            enable_trace=enable_trace,
            on_message=on_message,
            on_open=on_open,
            on_error=on_error,
            on_close=on_close
        )

        self._buffer = b""
        self._raw_buffer = b""
        self._is_chunked = False

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

    def connect(self):
        self.sock = self.create_socket()

        request_headers = self.get_socket_headers()

        for k, v in self.headers.items():
            request_headers.append(f"{k}: {v}")

        request = CRLF.join(request_headers) + CRLF_CRLF
        req = request.encode(DEFAULT_ENCODING)

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {req}")

        self.sock.sendall(req)

        response = b""
        crlf_crlf = CRLF_CRLF.encode(DEFAULT_ENCODING)
        while crlf_crlf not in response:
            chunk = self.sock.recv(WINDOW_SIZE)
            if not chunk:  # pragma: no cover
                raise SocketHandshakeError(
                    "Connection closed during handshake")
            response += chunk

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - {response}")

        if self.success_status_code not in response:  # pragma: no cover
            raise SocketHandshakeError(
                f"Handshake failed: {response.decode()}")

        # Detect chunked encoding and rescue body bytes read with the headers
        headers_end = response.index(crlf_crlf)
        headers = response[:headers_end]
        body_start = response[headers_end + len(crlf_crlf):]

        self._is_chunked = b"transfer-encoding: chunked" in headers.lower()

        if body_start:
            if self._is_chunked:
                self._raw_buffer = body_start
                self._decode_chunks()
            else:  # pragma: no cover
                self._buffer = body_start

        self.running = True
        self.recv_thread = threading.Thread(
            target=self.run,
            name=self.thread_name)
        self.recv_thread.daemon = True
        self.recv_thread.start()

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

        self.logger.debug(f"SSE send response: {status_code} - {data}")

    def prepare_data(self, buffer):

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] - [prepare data: input] {buffer}")
        sep = RECORD_SEPARATOR.encode(DEFAULT_ENCODING)
        if sep in buffer:
            decoded_strs = [parse_sse_to_json(x) for x in buffer.split(sep)]
            decoded_str = RECORD_SEPARATOR.join(decoded_strs)
        else:
            decoded_str = parse_sse_to_json(buffer)

        if self.is_trace_enabled():
            self.logger.debug(
                f"[TRACE] - [prepare data: output] {decoded_str}")

        return decoded_str

    def _decode_chunks(self):
        """Decode all complete HTTP chunks from _raw_buffer into _buffer."""
        while self._raw_buffer:
            crlf_pos = self._raw_buffer.find(b"\r\n")
            if crlf_pos == -1:  # pragma: no cover
                break

            # Strip chunk extensions (e.g. "1a;ext=foo\r\n")
            size_hex = self._raw_buffer[:crlf_pos].split(b";")[0].strip()

            if not size_hex:  # pragma: no cover
                # Empty line between chunks, skip it
                self._raw_buffer = self._raw_buffer[crlf_pos + 2:]
                continue

            try:
                chunk_size = int(size_hex, 16)
            except ValueError:  # pragma: no cover
                break

            if chunk_size == 0:  # pragma: no cover
                # Final chunk — server closed the stream
                raise SocketClosedError()

            data_start = crlf_pos + 2
            data_end = data_start + chunk_size

            # Need the full chunk data plus the trailing \r\n
            if len(self._raw_buffer) < data_end + 2:
                break

            self._buffer += self._raw_buffer[data_start:data_end]
            self._raw_buffer = self._raw_buffer[data_end + 2:]

    def _find_frame_end(self):
        """Return (index, end_length) for the first SSE frame boundary,
        or (-1, 0). Handles both LF-only (\\n\\n) and CRLF (\\r\\n\\r\\n)."""
        crlf = self._buffer.find(b"\r\n\r\n")
        lf = self._buffer.find(b"\n\n")
        if crlf == -1 and lf == -1:
            return -1, 0
        if crlf == -1:
            return lf, 2
        if lf == -1:
            return crlf, 4
        return (crlf, 4) if crlf < lf else (lf, 2)

    def _recv_frame(self):
        end_record = RECORD_SEPARATOR.encode(DEFAULT_ENCODING)

        while True:
            idx, end_len = self._find_frame_end()
            if idx != -1:
                break

            chunk = self.sock.recv(WINDOW_SIZE)
            if not chunk:  # pragma: no cover
                raise SocketClosedError()

            if self._is_chunked:
                self._raw_buffer += chunk
                self._decode_chunks()
            else:
                self._buffer += chunk

        if self.is_trace_enabled():
            self.logger.debug(f"[TRACE] [BUFFER] - {self._buffer}")

        frame_data = self._buffer[:idx]
        self._buffer = self._buffer[idx + end_len:]

        # Extract and concatenate data: fields from the SSE frame
        data_parts = []
        for line in frame_data.split(b"\n"):
            line = line.rstrip(b"\r")
            if line.startswith(b"data:"):
                data_parts.append(line[5:].lstrip(b" "))

        if not data_parts:  # pragma: no cover
            return None  # keep-alive or non-data frame

        data = b"".join(data_parts)

        # Strip SignalR record separator if present
        if end_record in data:
            data = data[:data.rindex(end_record)]

        if not data:  # pragma: no cover
            return None

        try:
            return self.prepare_data(data)
        except Exception as ex:
            self.logger.error(ex)
            raise ex

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
