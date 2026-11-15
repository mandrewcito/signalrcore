"""Minimal asyncio HTTP/1.1 client used by the async transports.

Only the features needed by SignalR are implemented: request/response,
chunked or content-length bodies, redirects, TLS and HTTP proxies
(absolute-form for plain connections, CONNECT tunnelling for TLS).
"""

import asyncio
import base64
import copy
import json
import ssl
import urllib.parse as parse
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from ...helpers import Helpers, RequestHelpers
from ...types import DEFAULT_ENCODING, CRLF, CRLF_CRLF

MAX_REDIRECTS = 5
READ_LIMIT = 1024 * 1024
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
BODY_STATUSES = (204, 304)


class HTTPConnectionError(OSError):
    pass


@dataclass
class AsyncHTTPResponse:
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def content(self) -> bytes:
        return self.body

    def json(self):
        response_body = self.body.decode(DEFAULT_ENCODING)
        return json.loads(response_body)\
            if len(response_body) > 0 else None


class AsyncHTTPConnection(object):
    """An open response whose body is read by the caller."""

    def __init__(
            self,
            status_code: int,
            headers: Dict[str, str],
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter):
        self.status_code = status_code
        self.headers = headers
        self.reader = reader
        self.writer = writer

    async def close(self) -> None:
        writer = getattr(self, "writer", None)
        if writer is None:
            return
        self.writer = None
        writer.close()
        try:
            await writer.wait_closed()
        except (AttributeError, ConnectionError, OSError):  # pragma: no cover
            pass

    @property
    def is_chunked(self) -> bool:
        return "chunked" in self.headers.get(
            "transfer-encoding", "").lower()

    async def read_body(self) -> bytes:
        try:
            if self.status_code in BODY_STATUSES:
                return b""

            if self.is_chunked:
                return await _read_chunked(self.reader)

            content_length = self.headers.get("content-length")

            if content_length is not None:
                length = int(content_length)
                return await self.reader.readexactly(length)\
                    if length > 0 else b""

            return await self.reader.read()
        finally:
            await self.close()


def _default_port(parsed) -> int:
    return parsed.port or (443 if parsed.scheme in ("https", "wss") else 80)


def _host_header(parsed) -> str:
    return parsed.netloc.rsplit("@", 1)[-1] or parsed.hostname


def _request_target(parsed) -> str:
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    return target


def _proxy_headers(proxy_info) -> Dict[str, str]:
    if proxy_info.username is None:
        return {}

    username = parse.unquote(proxy_info.username)
    password = parse.unquote(proxy_info.password or "")
    credentials = base64.b64encode(
        f"{username}:{password}".encode(DEFAULT_ENCODING)
    ).decode(DEFAULT_ENCODING)
    return {"Proxy-Authorization": "Basic " + credentials}


async def _open_connection(
        parsed,
        proxy_info,
        ssl_context: Optional[ssl.SSLContext],
        use_ssl: bool):
    """Opens the TCP (and TLS) connection, tunnelling through a proxy."""
    secure = parsed.scheme in ("https", "wss")

    if proxy_info is None:
        return await asyncio.open_connection(
            parsed.hostname,
            _default_port(parsed),
            ssl=ssl_context if secure else None,
            server_hostname=parsed.hostname if secure else None,
            limit=READ_LIMIT)

    proxy_host = proxy_info.hostname
    proxy_port = proxy_info.port or (
        443 if proxy_info.scheme == "https" else 80)

    reader, writer = await asyncio.open_connection(
        proxy_host, proxy_port, limit=READ_LIMIT)

    if secure:
        await _tunnel_through_proxy(
            reader, writer, proxy_info, parsed.hostname, _default_port(parsed))

        if use_ssl and ssl_context is not None:
            await _upgrade_to_tls(
                reader, writer, ssl_context, parsed.hostname)

    return reader, writer


async def _tunnel_through_proxy(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        proxy_info,
        host: str,
        port: int) -> None:
    target = f"{host}:{port}"
    headers = [f"CONNECT {target} HTTP/1.1", f"Host: {target}"]
    headers.extend(
        f"{name}: {value}"
        for name, value in _proxy_headers(proxy_info).items())

    writer.write(
        (CRLF.join(headers) + CRLF_CRLF).encode(DEFAULT_ENCODING))
    await writer.drain()

    response = await reader.readuntil(CRLF_CRLF.encode(DEFAULT_ENCODING))
    status_line = response.split(
        CRLF.encode(DEFAULT_ENCODING), 1)[0].decode(
            DEFAULT_ENCODING, errors="replace")
    status_parts = status_line.split()

    if len(status_parts) < 2 or status_parts[1] != "200":
        raise HTTPConnectionError(
            f"Proxy handshake failed: {status_line}")


async def _upgrade_to_tls(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        ssl_context: ssl.SSLContext,
        host: str) -> None:
    """Upgrades an existing stream (a proxy tunnel) to TLS."""
    loop = asyncio.get_running_loop()
    transport = writer.transport
    protocol = transport.get_protocol()

    new_transport = await loop.start_tls(
        transport, protocol, ssl_context, server_hostname=host)

    # StreamReader and StreamReaderProtocol keep their own references to
    # the original transport; point them at the TLS one.
    if hasattr(protocol, "_transport"):
        protocol._transport = new_transport
    if hasattr(reader, "_transport"):
        reader._transport = new_transport

    writer._transport = new_transport


def _build_request(
        method: str,
        parsed,
        headers: Dict[str, str],
        data: Optional[bytes],
        proxy_info) -> bytes:
    target = _request_target(parsed)

    if proxy_info is not None and parsed.scheme not in ("https", "wss"):
        # Plain HTTP through a proxy uses the absolute-form target.
        target = parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path or "/",
            parsed.params, parsed.query, ""))

    request_headers = copy.deepcopy(headers)
    request_headers.setdefault("Host", _host_header(parsed))

    if data is not None:
        request_headers.setdefault("Content-Length", str(len(data)))

    request = [f"{method} {target} HTTP/1.1"]
    request.extend(
        f"{name}: {value}" for name, value in request_headers.items())
    request.append(CRLF)

    payload = CRLF.join(request).encode(DEFAULT_ENCODING)
    if data is not None:
        payload += data
    return payload


def _parse_status_and_headers(raw: bytes) -> Tuple[int, Dict[str, str]]:
    if not raw:
        raise HTTPConnectionError("Empty response")

    text = raw.decode(DEFAULT_ENCODING, errors="replace")
    lines = text.split(CRLF)

    status_parts = lines[0].split()
    if len(status_parts) < 2:
        raise HTTPConnectionError(f"Invalid status line: {lines[0]}")

    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return int(status_parts[1]), headers


async def _read_chunked(reader: asyncio.StreamReader) -> bytes:
    body = b""

    while True:
        line = await reader.readuntil(CRLF.encode(DEFAULT_ENCODING))
        size_hex = line[:-2].split(b";")[0].strip()

        if not size_hex:  # pragma: no cover
            continue

        size = int(size_hex, 16)

        if size == 0:
            # Consume optional trailers up to the final blank line.
            while True:
                trailer = await reader.readuntil(
                    CRLF.encode(DEFAULT_ENCODING))
                if trailer in (
                        b"\r\n", b"\n"):  # pragma: no cover
                    break
            return body

        body += await reader.readexactly(size)
        await reader.readexactly(2)


async def open_request(
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        proxies: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[bytes] = None,
        ssl_context: Optional[ssl.SSLContext] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True) -> AsyncHTTPConnection:
    """Sends a request and returns once the response headers are read.

    The body is left unread so streaming transports can consume it. The
    returned connection owns the writer and must be closed by the caller.
    """
    headers = dict(headers or {})
    proxies = proxies or {}
    params = params or {}
    method = method.upper()

    requested_url = RequestHelpers.update_querystring(url, params)

    async def _open():
        current_url = requested_url
        current_method = method
        current_data = data

        for _ in range(MAX_REDIRECTS + 1):
            parsed = parse.urlparse(current_url)
            secure = parsed.scheme in ("https", "wss")
            proxy_info = Helpers.get_proxy_info(secure, proxies)
            use_ssl = ssl_context if secure else None

            reader, writer = await _open_connection(
                parsed, proxy_info, use_ssl, secure)

            try:
                payload = _build_request(
                    current_method,
                    parsed,
                    headers,
                    current_data,
                    proxy_info)

                writer.write(payload)
                await writer.drain()

                raw = await reader.readuntil(
                    CRLF_CRLF.encode(DEFAULT_ENCODING))
                status_code, response_headers = _parse_status_and_headers(raw)

                location = response_headers.get("location")

                if follow_redirects\
                        and status_code in REDIRECT_STATUSES\
                        and location:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except (ConnectionError, OSError):  # pragma: no cover
                        pass

                    current_url = parse.urljoin(current_url, location)

                    if status_code == 303 or (
                            status_code in (301, 302)
                            and current_method not in ("GET", "HEAD")):
                        current_method = "GET"
                        current_data = None
                        headers.pop("Content-Length", None)

                    continue

                return AsyncHTTPConnection(
                    status_code, response_headers, reader, writer)
            except BaseException:
                writer.close()
                try:
                    await writer.wait_closed()
                except (ConnectionError, OSError):  # pragma: no cover
                    pass
                raise

        raise HTTPConnectionError("Too many redirects")

    if timeout is None:
        return await _open()

    return await asyncio.wait_for(_open(), timeout=timeout)


async def request(
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        proxies: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[bytes] = None,
        timeout: Optional[float] = None,
        ssl_context: Optional[ssl.SSLContext] = None) -> AsyncHTTPResponse:
    """Performs a request and reads the whole body."""
    connection = await open_request(
        url,
        method=method,
        headers=headers,
        proxies=proxies,
        params=params,
        data=data,
        ssl_context=ssl_context,
        timeout=timeout)

    try:
        body = await connection.read_body()
    finally:
        await connection.close()

    return AsyncHTTPResponse(
        status_code=connection.status_code,
        headers=connection.headers,
        body=body)
