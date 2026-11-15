import asyncio
import os
import ssl
import unittest

from signalrcore.aio.transport.http import (
    HTTPConnectionError,
    _tunnel_through_proxy,
    open_request,
    request,
)
from signalrcore.helpers import Helpers

CERTIFICATES = os.path.join(
    os.path.dirname(__file__), "..", "..", "resources", "certificates")


class FakeServer(object):
    def __init__(self, handler):
        self.handler = handler
        self.server = None
        self.requests = []

    async def start(self, ssl_context=None):
        self.server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0, ssl=ssl_context)
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

    @property
    def port(self):
        return self.server.sockets[0].getsockname()[1]

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    async def close(self):
        self.server.close()
        await self.server.wait_closed()


async def read_request(reader):
    raw = await reader.readuntil(b"\r\n\r\n")
    return raw.decode("utf-8", errors="replace")


async def send_response(
        writer,
        status=200,
        headers=None,
        body=b"",
        reason="OK"):
    headers = headers or {}
    headers.setdefault("Content-Length", str(len(body)))
    lines = [f"HTTP/1.1 {status} {reason}"]
    lines.extend(f"{name}: {value}" for name, value in headers.items())
    writer.write(("\r\n".join(lines) + "\r\n\r\n").encode() + body)
    await writer.drain()


class AsyncHTTPTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.servers = []

    async def asyncTearDown(self):
        for server in self.servers:
            await server.close()

    async def server(self, handler, ssl_context=None):
        server = await FakeServer(handler).start(ssl_context)
        self.servers.append(server)
        return server

    async def test_content_length_response(self):
        async def handler(server, reader, writer):
            server.requests.append(await read_request(reader))
            await send_response(writer, body=b'{"ok": true}')

        server = await self.server(handler)

        response = await request(server.url + "/chat/negotiate", method="POST")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertIn("POST /chat/negotiate HTTP/1.1", server.requests[0])

    async def test_204_has_empty_body(self):
        async def handler(server, reader, writer):
            await read_request(reader)
            await send_response(writer, status=204, reason="No Content")

        server = await self.server(handler)

        response = await request(server.url + "/poll")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.body, b"")

    async def test_chunked_response(self):
        async def handler(server, reader, writer):
            await read_request(reader)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n"
                b"5\r\nhello\r\n"
                b"6\r\n world\r\n"
                b"0\r\n\r\n")
            await writer.drain()

        server = await self.server(handler)

        response = await request(server.url + "/stream")

        self.assertEqual(response.body, b"hello world")

    async def test_close_delimited_response(self):
        async def handler(server, reader, writer):
            await read_request(reader)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Connection: close\r\n\r\n"
                b"until the socket closes")
            await writer.drain()

        server = await self.server(handler)

        response = await request(server.url + "/stream")

        self.assertEqual(response.body, b"until the socket closes")

    async def test_error_status_is_returned(self):
        async def handler(server, reader, writer):
            await read_request(reader)
            await send_response(
                writer, status=401, reason="Unauthorized",
                body=b'{"error": "no"}')

        server = await self.server(handler)

        response = await request(server.url + "/negotiate", method="POST")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "no"})

    async def test_redirect_is_followed(self):
        async def handler(server, reader, writer):
            raw = await read_request(reader)
            if "GET /old" in raw:
                await send_response(
                    writer, status=302, reason="Found",
                    headers={"Location": "/new"})
            else:
                await send_response(writer, body=b"moved")

        server = await self.server(handler)

        response = await request(server.url + "/old")

        self.assertEqual(response.body, b"moved")

    async def test_timeout_cancels_the_request(self):
        async def handler(server, reader, writer):
            await read_request(reader)
            # Wait for the client to give up instead of blocking teardown.
            await reader.read(1)

        server = await self.server(handler)

        with self.assertRaises(asyncio.TimeoutError):
            await request(server.url + "/slow", timeout=0.05)

    async def test_open_request_leaves_body_unread(self):
        async def handler(server, reader, writer):
            await read_request(reader)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n"
                b"3\r\nabc\r\n")
            await writer.drain()
            await asyncio.sleep(0.2)

        server = await self.server(handler)

        connection = await open_request(server.url + "/stream")
        try:
            self.assertTrue(connection.is_chunked)
        finally:
            await connection.close()

    async def test_proxy_uses_absolute_form(self):
        requests = []

        async def handler(server, reader, writer):
            requests.append(await read_request(reader))
            await send_response(writer, body=b"proxied")

        proxy = await self.server(handler)

        response = await request(
            "http://example.invalid/chat",
            proxies={"http": proxy.url})

        self.assertEqual(response.body, b"proxied")
        self.assertIn(
            "GET http://example.invalid/chat HTTP/1.1", requests[0])

    async def test_tunnel_through_proxy(self):
        async def handler(server, reader, writer):
            server.requests.append(await read_request(reader))
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            await asyncio.sleep(0.1)

        proxy = await self.server(handler)

        reader, writer = await asyncio.open_connection(
            "127.0.0.1", proxy.port)
        try:
            await _tunnel_through_proxy(
                reader,
                writer,
                Helpers.get_proxy_info(
                    True, {"https": proxy.url}),
                "example.invalid",
                443)
        finally:
            writer.close()
            await writer.wait_closed()

        self.assertIn(
            "CONNECT example.invalid:443 HTTP/1.1", proxy.requests[0])

    async def test_tunnel_rejects_error_status(self):
        async def handler(server, reader, writer):
            await read_request(reader)
            writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            await writer.drain()

        proxy = await self.server(handler)

        reader, writer = await asyncio.open_connection(
            "127.0.0.1", proxy.port)
        try:
            with self.assertRaises(HTTPConnectionError):
                await _tunnel_through_proxy(
                    reader,
                    writer,
                    Helpers.get_proxy_info(
                        True, {"https": proxy.url}),
                    "example.invalid",
                    443)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_tls_connection(self):
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(
            os.path.join(CERTIFICATES, "localhost.crt"),
            os.path.join(CERTIFICATES, "localhost.key"))

        async def handler(server, reader, writer):
            await read_request(reader)
            await send_response(writer, body=b"secure")

        server = await self.server(handler, server_context)

        client_context = ssl.create_default_context(
            cafile=os.path.join(CERTIFICATES, "ca.crt"))

        response = await request(
            f"https://localhost:{server.port}/secure",
            ssl_context=client_context)

        self.assertEqual(response.body, b"secure")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
