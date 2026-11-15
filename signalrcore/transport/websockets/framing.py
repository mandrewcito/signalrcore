import base64
import hashlib
import os
import struct

from ...types import DEFAULT_ENCODING, CRLF

WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# SignalR broadcasts can be large, but no message should be able to make
# the client allocate an unbounded buffer from the frame header alone.
MAX_PAYLOAD_SIZE = 16 * 1024 * 1024


def build_frame(payload: bytes, opcode: int = 0x1) -> bytes:
    """Builds a masked, unfragmented client WebSocket frame."""
    header = bytes([0x80 | opcode])
    length = len(payload)

    if length <= 125:
        header += bytes([0x80 | length])
    elif length <= 65535:
        header += bytes([0x80 | 126]) + struct.pack(">H", length)
    else:
        header += bytes([0x80 | 127]) + struct.pack(">Q", length)

    masking_key = os.urandom(4)
    masked_payload = bytes(
        b ^ masking_key[i % 4]
        for i, b in enumerate(payload))
    return header + masking_key + masked_payload


def parse_handshake_headers(response: bytes) -> dict:
    """Parses the headers of a WebSocket handshake response."""
    headers = {}

    for line in response.decode(
            DEFAULT_ENCODING, errors="replace").split(CRLF):
        if ":" not in line:
            continue

        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return headers


def websocket_accept(key: str) -> str:
    return base64.b64encode(
        hashlib.sha1(
            (key + WEBSOCKET_GUID).encode(DEFAULT_ENCODING)
        ).digest()
    ).decode(DEFAULT_ENCODING)
