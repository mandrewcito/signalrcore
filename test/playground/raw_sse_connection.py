import asyncio
import json
import ssl
from urllib.parse import urlparse, urlencode


async def http_request(method, url, headers=None, body=b"", use_ssl=False):
    headers = headers or {}

    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if use_ssl else 80)

    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    ssl_ctx = ssl.create_default_context() if use_ssl else None
    reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)

    headers.setdefault("Host", host)
    headers.setdefault("Content-Length", str(len(body)))
    headers.setdefault("Connection", "close")

    request = (
        f"{method} {path} HTTP/1.1\r\n"
        + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        + "\r\n"
    ).encode() + body

    writer.write(request)
    await writer.drain()

    response = await reader.read()
    writer.close()
    await writer.wait_closed()

    return response


async def negotiate(base_url):
    negotiate_url = base_url.rstrip("/") + "/negotiate"

    headers = {
        "Content-Type": "application/json",
    }

    response = await http_request("POST", negotiate_url, headers)
    body = response.split(b"\r\n\r\n", 1)[1]

    data = json.loads(body.decode())

    print("negotiate:", data)

    return data


async def sse_connect(url, headers):
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 80

    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query

    reader, writer = await asyncio.open_connection(host, port)

    headers = headers.copy()
    headers.update({
        "Host": host,
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    })

    request = (
        f"GET {path} HTTP/1.1\r\n"
        + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        + "\r\n"
    )

    writer.write(request.encode())
    await writer.drain()

    # Skip HTTP headers
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break

    return reader, writer


async def read_sse(reader):
    while True:
        line = await reader.readline()
        if not line:
            break

        line = line.strip()
        if line.startswith(b"data:"):
            payload = line[5:].strip()
            yield payload


async def send_signalr_message(url, payload: bytes):
    headers = {
        "Content-Type": "application/octet-stream",
    }
    await http_request("POST", url, headers, payload)


async def main():
    base_url = "http://localhost:5000/chathub"

    # 1. Negotiate
    negotiation = await negotiate(base_url)
    connection_id = negotiation["connectionId"]

    # 2. Build connect URL
    query = urlencode({
        "id": connection_id
    })
    connect_url = f"{base_url}?{query}"

    # 3. SSE connect
    reader, writer = await sse_connect(connect_url, {})

    # 4. Send handshake
    handshake = json.dumps({
        "protocol": "json",
        "version": 1
    }).encode() + b"\x1e"

    await send_signalr_message(connect_url, handshake)

    print("Connected via SSE")

    # 5. Read messages
    async for message in read_sse(reader):
        if message == b"{}":
            print("Handshake OK")
            continue

        print("RAW:", message)

        try:
            data = json.loads(message.decode().rstrip("\x1e"))
            print("Parsed:", data)
        except Exception:
            pass

asyncio.run(main())
