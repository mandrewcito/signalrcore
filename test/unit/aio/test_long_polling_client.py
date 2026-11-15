import asyncio
import unittest

from signalrcore.aio.transport.long_polling.client import (
    AIOLongPollingBinaryClient,
    AIOLongPollingTextClient,
)


class FakeLongPollingServer(object):
    def __init__(self, handler):
        self.handler = handler
        self.server = None
        self.requests = []
        self.delete_received = asyncio.Event()

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0)
        return self

    async def _handle(self, reader, writer):
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
            length = 0
            for line in raw.decode().split("\r\n"):
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":", 1)[1])

            body = await reader.readexactly(length) if length else b""
            request = (raw, body)
            self.requests.append(request)
            await self.handler(self, request, writer)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"\
            "/chatHub"

    async def close(self):
        self.server.close()
        await self.server.wait_closed()


async def send(writer, status=200, body=b"", reason="OK"):
    writer.write(
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    await writer.drain()


class AIOLongPollingClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.servers = []
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.close()
        for server in self.servers:
            await server.close()

    async def build_client(
            self,
            handler,
            client_class=AIOLongPollingTextClient,
            **kwargs):
        server = await FakeLongPollingServer(handler).start()
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

        client = client_class(
            url=server.url,
            connection_id="connection-id",
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
            **kwargs)
        self.clients.append(client)

        await client.connect()
        await asyncio.wait_for(opened.wait(), timeout=1)

        return client, server, messages, closed, errors

    async def test_polls_and_splits_records(self):
        calls = {"count": 0}

        async def handler(server, request, writer):
            calls["count"] += 1
            if calls["count"] == 1:
                await send(writer, body=b"one\x1etwo\x1e")
            else:
                await send(writer, status=204, reason="No Content")

        client, server, messages, closed, errors =\
            await self.build_client(handler)

        await asyncio.wait_for(closed.wait(), timeout=1)

        self.assertEqual(messages, ["one", "two"])
        self.assertEqual(errors, [])
        self.assertIn("id=connection-id", server.requests[0][0].decode())

    async def test_204_closes_connection(self):
        async def handler(server, request, writer):
            await send(writer, status=204, reason="No Content")

        _, _, _, closed, errors = await self.build_client(handler)

        await asyncio.wait_for(closed.wait(), timeout=1)
        self.assertEqual(errors, [])

    async def test_404_closes_connection(self):
        async def handler(server, request, writer):
            await send(writer, status=404, reason="Not Found")

        _, _, _, closed, _ = await self.build_client(handler)

        await asyncio.wait_for(closed.wait(), timeout=1)

    async def test_timeout_retries(self):
        calls = {"count": 0}

        async def handler(server, request, writer):
            calls["count"] += 1
            if calls["count"] == 1:
                await asyncio.sleep(0.2)
                await send(writer, status=204, reason="No Content")
            else:
                await send(writer, status=204, reason="No Content")

        _, _, _, closed, _ = await self.build_client(
            handler, timeout=0.05)

        await asyncio.wait_for(closed.wait(), timeout=1)

        self.assertGreaterEqual(calls["count"], 2)

    async def test_send_posts_body(self):
        release = asyncio.Event()

        async def handler(server, request, writer):
            raw, body = request
            if raw.startswith(b"POST"):
                await send(writer, body=b"{}")
            elif raw.startswith(b"GET"):
                await release.wait()
                await send(writer, status=204, reason="No Content")
            else:
                await send(writer)

        client, server, _, closed, _ = await self.build_client(handler)

        await client.send("payload")
        release.set()

        await asyncio.wait_for(closed.wait(), timeout=1)

        post = [r for r in server.requests if r[0].startswith(b"POST")][0]
        self.assertEqual(post[1], b"payload")

    async def test_binary_client_returns_bytes(self):
        async def handler(server, request, writer):
            if request[0].startswith(b"GET"):
                await send(writer, body=b"\x01\x02\x1e")
            else:
                await send(writer, body=b"{}")

        client, _, messages, _, _ = await self.build_client(
            handler, AIOLongPollingBinaryClient)

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, [b"\x01\x02"])

    async def test_close_sends_delete(self):
        async def handler(server, request, writer):
            raw, _ = request
            if raw.startswith(b"GET"):
                await asyncio.sleep(0.5)
            elif raw.startswith(b"DELETE"):
                server.delete_received.set()
                await send(writer)
            else:
                await send(writer)

        client, server, _, _, _ = await self.build_client(handler)

        await client.close()

        await asyncio.wait_for(server.delete_received.wait(), timeout=1)
        self.assertTrue(client.is_connection_closed())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
