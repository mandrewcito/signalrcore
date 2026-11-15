import asyncio
import base64
import hashlib
import struct
import unittest

from signalrcore.aio.transport.websockets.client import AIOWebSocketClient
from signalrcore.transport.sockets.errors import SocketHandshakeError
from signalrcore.transport.websockets.framing import WEBSOCKET_GUID


def server_frame(payload: bytes, opcode=0x1, fin=True) -> bytes:
    header = bytes([(0x80 if fin else 0) | opcode])
    length = len(payload)

    if length <= 125:
        header += bytes([length])
    elif length <= 65535:
        header += bytes([126]) + struct.pack(">H", length)
    else:
        header += bytes([127]) + struct.pack(">Q", length)

    return header + payload


async def read_client_frame(reader):
    header = await reader.readexactly(2)
    masked = header[1] & 0x80
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F

    if length == 126:
        length = struct.unpack(">H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", await reader.readexactly(8))[0]

    mask = await reader.readexactly(4) if masked else b"\x00" * 4
    payload = await reader.readexactly(length)
    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload


class FakeWebSocketServer(object):
    def __init__(self, after_handshake=None, accept_override=None):
        self.after_handshake = after_handshake
        self.accept_override = accept_override
        self.server = None
        self.request_headers = b""
        self.sent_key = None

    async def start(self):
        self.server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0)
        return self

    async def _handle(self, reader, writer):
        try:
            self.request_headers = await reader.readuntil(b"\r\n\r\n")

            for line in self.request_headers.decode().split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    self.sent_key = line.split(":", 1)[1].strip()

            accept = self.accept_override or base64.b64encode(
                hashlib.sha1(
                    (self.sent_key + WEBSOCKET_GUID).encode()
                ).digest()).decode()

            writer.write(
                b"HTTP/1.1 101 Switching Protocols\r\n"
                b"Upgrade: websocket\r\n"
                b"Connection: Upgrade\r\n"
                b"Sec-WebSocket-Accept: " + accept.encode()
                + b"\r\n\r\n")
            await writer.drain()

            if self.after_handshake is not None:
                await self.after_handshake(self, reader, writer)
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
        return f"ws://127.0.0.1:{self.port}/chatHub"

    async def close(self):
        self.server.close()
        await self.server.wait_closed()


class AIOWebSocketClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.servers = []
        self.client = None

    async def asyncTearDown(self):
        if self.client is not None:
            await self.client.close()
        for server in self.servers:
            await server.close()

    async def build_client(self, handler, **kwargs):
        server = await FakeWebSocketServer(handler).start()
        self.servers.append(server)

        opened = asyncio.Event()
        messages = []
        closed = asyncio.Event()
        errors = []

        async def on_open():
            opened.set()

        async def on_message(app, message):
            messages.append(message)

        async def on_close():
            closed.set()

        async def on_error(error):
            errors.append(error)

        self.client = AIOWebSocketClient(
            url=server.url,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
            **kwargs)

        await self.client.connect()
        await asyncio.wait_for(opened.wait(), timeout=1)

        return server, messages, closed, errors

    async def test_handshake_and_text_message(self):
        async def handler(server, reader, writer):
            self.assertEqual(await read_client_frame(reader), (0x1, b"hello"))
            writer.write(server_frame(b"world"))
            await writer.drain()
            await reader.read(1)

        server, messages, closed, errors = await self.build_client(handler)

        await self.client.send("hello")

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, ["world"])
        self.assertIn(b"Sec-WebSocket-Key:", server.request_headers)
        self.assertFalse(closed.is_set())
        self.assertEqual(errors, [])

    async def test_binary_message(self):
        async def handler(server, reader, writer):
            opcode, payload = await read_client_frame(reader)
            self.assertEqual(opcode, 0x2)
            writer.write(server_frame(payload, opcode=0x2))
            await writer.drain()
            await reader.read(1)

        _, messages, _, _ = await self.build_client(handler, is_binary=True)

        await self.client.send(b"\x01\x02", opcode=0x2)

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, [b"\x01\x02"])

    async def test_fragmented_message(self):
        async def handler(server, reader, writer):
            writer.write(server_frame(b"hello ", fin=False, opcode=0x1))
            writer.write(server_frame(b"world", fin=True, opcode=0x0))
            await writer.drain()
            await reader.read(1)

        _, messages, _, _ = await self.build_client(handler)

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, ["hello world"])

    async def test_partial_frames(self):
        async def handler(server, reader, writer):
            frame = server_frame(b"split")
            for byte in frame:
                writer.write(bytes([byte]))
                await writer.drain()
                await asyncio.sleep(0)
            await reader.read(1)

        _, messages, _, _ = await self.build_client(handler)

        while not messages:
            await asyncio.sleep(0.01)

        self.assertEqual(messages, ["split"])

    async def test_ping_is_answered_with_pong(self):
        received = asyncio.Event()

        async def handler(server, reader, writer):
            writer.write(server_frame(b"ping", opcode=0x9))
            await writer.drain()

            opcode, payload = await read_client_frame(reader)
            self.assertEqual((opcode, payload), (0xA, b"ping"))
            received.set()
            await reader.read(1)

        await self.build_client(handler)

        await asyncio.wait_for(received.wait(), timeout=1)

    async def test_server_close_triggers_on_close(self):
        async def handler(server, reader, writer):
            writer.write(server_frame(b"", opcode=0x8))
            await writer.drain()
            await reader.read(1)

        _, _, closed, errors = await self.build_client(handler)

        await asyncio.wait_for(closed.wait(), timeout=1)
        self.assertEqual(errors, [])

    async def test_invalid_accept_raises_handshake_error(self):
        server = await FakeWebSocketServer(
            None, accept_override="invalid").start()
        self.servers.append(server)

        self.client = AIOWebSocketClient(url=server.url)

        with self.assertRaises(SocketHandshakeError):
            await self.client.connect()

    async def test_oversized_payload_closes(self):
        async def handler(server, reader, writer):
            writer.write(
                b"\x81\x7f" + struct.pack(
                    ">Q", 16 * 1024 * 1024 + 1))
            await writer.drain()
            await reader.read(1)

        _, _, closed, _ = await self.build_client(handler)

        await asyncio.wait_for(closed.wait(), timeout=1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
