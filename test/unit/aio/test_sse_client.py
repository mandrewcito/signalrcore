import asyncio
import unittest

from signalrcore.aio.transport.sse.client import AIOSSEClient
from signalrcore.transport.sockets.errors import SocketHandshakeError

SSE_HEADERS = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/event-stream\r\n"
    b"Cache-Control: no-cache\r\n"
    b"Connection: keep-alive\r\n\r\n")


def chunk(payload: bytes, extension: bytes = b"") -> bytes:
    size = format(len(payload), "x").encode()
    extension = b";" + extension if extension else b""
    return size + extension + b"\r\n" + payload + b"\r\n"


class FakeSSEServer(object):
    def __init__(self, handler):
        self.handler = handler
        self.server = None
        self.requests = []
        self.post_body = None
        self.post_received = asyncio.Event()

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0)
        return self

    async def _handle(self, reader, writer):
        try:
            await self.handler(self, reader, writer)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def read_request_headers(self, reader):
        raw = await reader.readuntil(b"\r\n\r\n")
        self.requests.append(raw.decode("utf-8", errors="replace"))
        return raw

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"\
            "/chatHub"

    async def close(self):
        self.server.close()
        await self.server.wait_closed()


class AIOSSEClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clients = []
        self.servers = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        for server in self.servers:
            await server.close()

    async def build_client(self, handler):
        server = await FakeSSEServer(handler).start()
        self.servers.append(server)

        opened = asyncio.Event()
        closed = asyncio.Event()
        messages = []
        errors = []

        async def on_open():
            opened.set()

        async def on_message(app, message):
            messages.append(message)

        async def on_close():
            closed.set()

        async def on_error(error):
            errors.append(error)

        client = AIOSSEClient(
            url=server.url,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error)
        client._test_server = server
        self.clients.append(client)

        await client.connect()
        await asyncio.wait_for(opened.wait(), timeout=1)

        return client, messages, closed, errors

    async def test_receives_split_frames(self):
        async def handler(server, reader, writer):
            await server.read_request_headers(reader)
            writer.write(SSE_HEADERS + b'data: {"type":1}\x1e\r\n')
            await writer.drain()
            await asyncio.sleep(0.01)
            writer.write(b'\r\ndata: {"type":2}\x1e\r\n\r\n')
            await writer.drain()
            await reader.read(1)

        _, messages, _, _ = await self.build_client(handler)

        while len(messages) < 2:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, ['{"type":1}', '{"type":2}'])

    async def test_chunked_frames_with_extensions(self):
        async def handler(server, reader, writer):
            await server.read_request_headers(reader)
            writer.write(
                SSE_HEADERS.replace(
                    b"Connection: keep-alive\r\n",
                    b"Connection: keep-alive\r\n"
                    b"Transfer-Encoding: chunked\r\n"))
            writer.write(
                chunk(
                    b'data: {"type":1}\x1e\r\n\r\n',
                    extension=b"ext=foo"))
            await writer.drain()
            await reader.read(1)

        _, messages, _, _ = await self.build_client(handler)

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, ['{"type":1}'])

    async def test_keepalive_frame_is_ignored(self):
        async def handler(server, reader, writer):
            await server.read_request_headers(reader)
            writer.write(SSE_HEADERS + b": keepalive\r\n\r\n")
            await writer.drain()
            await asyncio.sleep(0.01)
            writer.write(b'data: {"type":3}\x1e\r\n\r\n')
            await writer.drain()
            await reader.read(1)

        _, messages, _, _ = await self.build_client(handler)

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, ['{"type":3}'])

    async def test_multiple_records_in_one_frame(self):
        async def handler(server, reader, writer):
            await server.read_request_headers(reader)
            writer.write(
                SSE_HEADERS + b'data: {"type":1}\x1e{"type":2}\x1e\r\n\r\n')
            await writer.drain()
            await reader.read(1)

        _, messages, _, _ = await self.build_client(handler)

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, ['{"type":1}\x1e{"type":2}'])

    async def test_unauthorized_handshake_raises(self):
        async def handler(server, reader, writer):
            await server.read_request_headers(reader)
            writer.write(b"HTTP/1.1 401 Unauthorized\r\n\r\n")
            await writer.drain()

        server = await FakeSSEServer(handler).start()
        self.servers.append(server)

        client = AIOSSEClient(url=server.url)
        self.clients.append(client)

        with self.assertRaises(SocketHandshakeError):
            await client.connect()

    async def test_send_posts_message(self):
        async def handler(server, reader, writer):
            raw = await server.read_request_headers(reader)
            if raw.startswith(b"POST"):
                length = 0
                for line in raw.decode().split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        length = int(line.split(":", 1)[1])
                server.post_body = await reader.readexactly(length)
                server.post_received.set()
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Length: 2\r\n\r\n{}")
                await writer.drain()
                return

            writer.write(SSE_HEADERS)
            await writer.drain()
            await reader.read(1)

        client, _, _, _ = await self.build_client(handler)

        await client.send('{"type":1}\x1e')

        await asyncio.wait_for(
            client._test_server.post_received.wait(), timeout=1)

        self.assertFalse(client.is_connection_closed())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
