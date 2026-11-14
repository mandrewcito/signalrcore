import ssl
import unittest

from signalrcore.transport.sockets.base_socket_client import BaseSocketClient
from signalrcore.transport.sockets.errors import\
    NoHeaderException, SocketClosedError


class FakeSocketClient(BaseSocketClient):
    def __init__(self, error, is_closing=False):
        super(FakeSocketClient, self).__init__(
            thread_name="fake socket client",
            success_status_code=b"101",
            on_open=self._noop,
            on_close=self._on_close,
            on_error=self._on_error)
        self.error = error
        self.is_closing = is_closing
        self.running = True
        self.closed = False
        self.received_error = None

    def _noop(self):
        pass

    def _on_close(self):
        self.closed = True

    def _on_error(self, error):
        self.received_error = error

    def _recv_frame(self):
        raise self.error


class SocketErrorClassificationTest(unittest.TestCase):
    def run_client(self, error, is_closing=False):
        client = FakeSocketClient(error, is_closing)
        client.run()
        return client

    def assert_closed(self, error):
        client = self.run_client(error)

        self.assertTrue(client.closed)
        self.assertIsNone(client.received_error)
        self.assertFalse(client.running)

    def assert_error(self, error):
        client = self.run_client(error)

        self.assertFalse(client.closed)
        self.assertIs(client.received_error, error)
        self.assertFalse(client.running)

    def test_connection_reset_triggers_close(self):
        self.assert_closed(ConnectionResetError(104, "Connection reset"))

    def test_broken_pipe_triggers_close(self):
        self.assert_closed(BrokenPipeError(32, "Broken pipe"))

    def test_ssl_error_triggers_close(self):
        self.assert_closed(ssl.SSLError("SSL connection closed"))

    def test_socket_error_triggers_close(self):
        self.assert_closed(OSError(9, "Bad file descriptor"))

    def test_socket_closed_error_triggers_close(self):
        self.assert_closed(SocketClosedError())

    def test_no_header_triggers_close(self):
        self.assert_closed(NoHeaderException())

    def test_non_os_error_triggers_error(self):
        self.assert_error(ValueError("bad frame"))

    def test_errors_are_suppressed_while_closing(self):
        client = self.run_client(
            ConnectionResetError(104, "Connection reset"),
            is_closing=True)

        self.assertFalse(client.closed)
        self.assertIsNone(client.received_error)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
