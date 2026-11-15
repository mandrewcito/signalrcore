---
layout: default
title: AsyncIO (AIO)
nav_order: 5
---

# AsyncIO (AIO)
{: .no_toc }

## Table of Contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Overview

`AIOHubConnectionBuilder` creates an `async`/`await` native SignalR connection. Every network operation is a coroutine and must be awaited:

- `start()` and `stop()`
- `send()` and `invoke()`
- `stream()`
- `AIOSubject.next()`, `start()` and `complete()`

The AIO client is implemented with the standard library `asyncio` module only. It uses the same transports, protocols and configuration options as the synchronous client, without adding an `aiohttp` or `websockets` dependency.

Supported features:

- WebSockets, Server-Sent Events and Long Polling transports
- JSON and MessagePack protocols
- Access token authentication, with synchronous or coroutine token factories
- HTTP proxies (`absolute-form` requests and `CONNECT` tunnelling for TLS)
- Custom SSL contexts and certificate verification options
- Server-to-client and client-to-server streaming
- Automatic reconnection and keep-alive as asyncio background tasks
- Synchronous or asynchronous event, lifecycle and stream callbacks

Use the connection from a running event loop. Blocking operations, such as a synchronous login HTTP request, should be moved off the event loop with `asyncio.to_thread`.

---

## Quick Start

```python
import asyncio
import logging

from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder


async def main():
    hub = AIOHubConnectionBuilder()\
        .with_url(
            "wss://localhost:5001/chatHub",
            options={"verify_ssl": False})\
        .configure_logging(logging.INFO)\
        .build()

    async def on_message(arguments):
        print("Received:", arguments)

    hub.on("ReceiveMessage", on_message)

    await hub.start()

    try:
        await hub.send("SendMessage", ["user", "Hello from asyncio!"])
        await asyncio.sleep(1)
    finally:
        await hub.stop()


asyncio.run(main())
```

---

## Creating a Connection

```python
from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder

hub = AIOHubConnectionBuilder()\
    .with_url(server_url, options=options)\
    .configure_logging(logging.DEBUG, socket_trace=True)\
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    })\
    .build()
```

The `options` dictionary accepts the same entries as the synchronous builder:

| Option | Description |
|--------|-------------|
| `transport` | Preferred `HttpTransportType` (`web_sockets`, `server_sent_events`, `long_polling`) |
| `verify_ssl` | Boolean. Verifies the server certificate when `True` |
| `ssl_context` | Custom `ssl.SSLContext`. Mutually exclusive with `verify_ssl` |
| `headers` | Extra headers sent during negotiation and transport requests |
| `access_token_factory` | Callable returning the bearer token. It may be a coroutine function |
| `skip_negotiation` | Skip the negotiate request and connect directly |

---

## Transports

The server chooses the transport during negotiation. Use `transport` to force one of the supported transports:

```python
from signalrcore.types import HttpTransportType

hub = AIOHubConnectionBuilder()\
    .with_url(
        "https://localhost:5001/chatHub",
        options={
            "verify_ssl": False,
            "transport": HttpTransportType.long_polling
        })\
    .build()
```

The URL may use `ws`/`wss` or `http`/`https` schemes; the AIO transports normalize the scheme they need. Server-Sent Events and Long Polling use HTTP requests, while WebSockets use the upgraded socket.

MessagePack is selected with the protocol builder, exactly like the synchronous client:

```python
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol

hub = AIOHubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False})\
    .with_hub_protocol(MessagePackHubProtocol())\
    .build()
```

MessagePack requires a transport and server that offer the `Binary` transfer format. Server-Sent Events is a text-only transport, so use WebSockets or Long Polling for MessagePack.

---

## Starting and Stopping

```python
started = await hub.start()

# ... use the connection ...

await hub.stop()
```

`start()` returns `True` when the connection reaches the `connected` state and `False` when it is already connected. `stop()` is safe to call before `start()`: a missing transport counts as disconnected and the call returns immediately.

`start()` waits until the handshake completes for at most `AIO_CONNECTION_TIMEOUT` (30 seconds by default). Negotiation and the transport connection have their own bounds. `stop()` bounds client shutdown with `AIO_CLOSE_TIMEOUT` (10 seconds by default). If a stage does not complete, a built-in `TimeoutError` is raised instead of hanging. Exceptions raised by the underlying start/stop are propagated to the caller.

You can also wait for a state explicitly. This is useful after external connection events or during reconnection:

```python
from signalrcore.transport.base_transport import TransportState

await hub.wait_until_state(TransportState.connected, timeout=10)
await hub.wait_until_state(TransportState.disconnected, timeout=10)
```

Without a timeout, `wait_until_state()` waits indefinitely. The available states are `disconnected`, `connecting`, `connected` and `reconnecting`.

---

## Callbacks

Event and lifecycle callbacks may be plain functions or coroutine functions. Coroutine callbacks are awaited before message processing continues, so they can safely perform asynchronous work.

```python
async def on_open():
    print("Connected")

def on_close():
    print("Disconnected")

async def on_message(arguments):
    await asyncio.sleep(0)
    print("Message:", arguments)

hub.on_open(on_open)
hub.on_close(on_close)
hub.on_reconnect(lambda: print("Reconnected"))
hub.on_error(lambda message: print("Hub error:", message))
hub.on("ReceiveMessage", on_message)
```

Keep callbacks fast. Blocking the event loop with `time.sleep()` or synchronous network calls prevents the transport keep-alive and message reader from running; use `await asyncio.sleep()` and async clients instead.

`on_error` receives a completion or binding-failure message. Hub method exceptions for an invocation that has no stream handler are reported through this connection-level callback.

---

## Sending and Invoking

Use `invoke()` for server methods. `send()` remains available as a deprecated alias:

```python
result = await hub.invoke("SendMessage", ["user", "Hello"])
print(result.invocation_id)
```

An optional completion callback can be synchronous or asynchronous. It receives the invocation completion message:

```python
async def on_invocation(message):
    print("Invocation finished:", message.invocation_id)

await hub.invoke(
    "SendMessage",
    ["user", "Hello"],
    on_invocation=on_invocation)
```

`invoke()`, `send()` and `stream()` require a running transport. If the connection was never started, is stopped, or is reconnecting, they raise `HubConnectionError`.

---

## Server-to-Client Streaming

`stream()` is a coroutine, so await it before subscribing:

```python
import asyncio

received = []
finished = asyncio.Event()

async def on_next(item):
    received.append(item)

def on_complete(_):
    finished.set()

async def on_error(error):
    print("Stream error:", error)
    finished.set()

stream = await hub.stream("Counter", [10, 500])

stream.subscribe({
    "next": on_next,
    "complete": on_complete,
    "error": on_error
})

await finished.wait()
```

The `subscribe()` dictionary must contain all three callbacks: `next`, `complete` and `error`. Each callback may be synchronous or asynchronous.

Stream items can arrive very quickly, sometimes before `subscribe()` runs. The AIO stream handler buffers events received before subscription and delivers them in order once the callbacks are registered, so the first item is not lost.

---

## Client-to-Server Streaming

Use `AIOSubject` for client-to-server streams. All its operations are coroutines:

```python
from signalrcore.aio.subject import AIOSubject

subject = AIOSubject()

await hub.send("UploadStream", subject)

for item in ["chunk-0", "chunk-1", "chunk-2"]:
    await subject.next(item)

await subject.complete()
```

Sends are serialized with an `asyncio.Lock`, preserving stream order even when several coroutines produce items concurrently. The constructor accepts a lock acquisition timeout:

```python
subject = AIOSubject(timeout=10)
```

A timeout raises the built-in `TimeoutError`. A failed send always releases the lock.

The thread-based `signalrcore.subject.Subject` is not compatible with the asyncio connection. Passing it to `invoke()` or `send()` raises a `TypeError` telling you to use `AIOSubject`.

---

## Authentication

Pass a token factory in `options`. It may be a normal function or a coroutine function:

```python
async def get_token():
    response = await fetch_token()
    return response["token"]

hub = AIOHubConnectionBuilder()\
    .with_url(
        server_url,
        options={
            "verify_ssl": False,
            "access_token_factory": get_token,
            "headers": {"X-Client": "signalrcore"}
        })\
    .build()
```

The token is fetched before connecting and sent as an `Authorization: Bearer <token>` header. If the factory raises, `start()` propagates the exception and does not connect. For a blocking synchronous login function, wrap the call with `asyncio.to_thread` inside an async factory.

---

## Proxies and TLS

Configure proxies with `configure_proxies()`:

```python
hub = AIOHubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False})\
    .configure_proxies({
        "http": "http://proxy.example.com:8080",
        "https": "http://proxy.example.com:8080"
    })\
    .build()
```

Plain HTTP requests use the absolute-form request target. HTTPS and WSS connections are tunnelled with `CONNECT`, then upgraded to TLS. Proxy credentials may be embedded in the proxy URL as `http://user:password@host:port`.

For certificate configuration, either disable verification with `verify_ssl: False` for local development, or pass a prepared context:

```python
import ssl

context = ssl.create_default_context(cafile="ca.crt")

hub = AIOHubConnectionBuilder()\
    .with_url(server_url, options={"ssl_context": context})\
    .build()
```

Use only one of `verify_ssl` and `ssl_context`. For certificate setup details, see the [Custom Client Certificates](articles/custom-client-cert) article.

---

## Reconnection and Keep-Alive

Automatic reconnection works the same way as in the synchronous client, but the reconnection loop and keep-alive loop run as asyncio tasks:

```python
hub = AIOHubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False})\
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    })\
    .build()
```

Two strategies are available:

| Strategy | Configuration |
|----------|---------------|
| `raw` | `reconnect_interval` seconds between attempts and `max_attempts` |
| `interval` | `intervals` list, for example `[1, 2, 4, 8]` |

Use `on_reconnect` and `wait_until_state()` to react to reconnection:

```python
async def reconnected():
    print("Connection restored")
    await hub.wait_until_state(TransportState.connected, timeout=10)

hub.on_reconnect(reconnected)
```

`keep_alive_interval` controls how often the client pings the server when no messages have been received. Stop the connection with `await hub.stop()` to cancel pending reconnection and keep-alive tasks.

---

## Timeouts

The AIO client bounds each connection stage so a broken server cannot hang a coroutine forever:

| Constant | Default | Scope |
|----------|---------|-------|
| `AIO_CONNECTION_TIMEOUT` | 30 s | Waiting for the hub handshake after `start()` |
| `AIO_CONNECT_TIMEOUT` | 30 s | Opening the transport connection |
| `AIO_NEGOTIATE_TIMEOUT` | 30 s | Negotiate request |
| `AIO_CLOSE_TIMEOUT` | 10 s | Closing the transport client |
| `REQUEST_TIMEOUT` | 100 s | Long Polling request |

Operation-specific values can be passed to `wait_until_state()` and `AIOSubject(timeout=...)`. A timeout raises the built-in `TimeoutError`.

---

## Notes

- The synchronous API is unchanged. The AIO client lives under `signalrcore.aio` and shares the message, protocol and transport selection code with the synchronous client.
- Use `asyncio.Event`, `asyncio.Lock` and other asyncio primitives in tests and callbacks. Blocking thread locks stall the event loop.
- Asyncio debug mode (`PYTHONASYNCIODEBUG=1`) is useful when a callback blocks the loop or a task is left pending.
