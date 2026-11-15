---
layout: default
title: Streaming
nav_order: 4
---

# Streaming
{: .no_toc }

## Table of Contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Server-to-Client Streaming

Use `hub_connection.stream()` to subscribe to a server-side streaming method. The subscription object accepts three callbacks:

| Callback | Description |
|----------|-------------|
| `next` | Called for each item streamed from the server |
| `complete` | Called with the completion message when the stream ends successfully |
| `error` | Called with the message when the stream encounters an error |

```python
hub_connection.stream(
    "Counter",
    [len(self.items), 500]  # method arguments
).subscribe({
    "next": self.on_next,
    "complete": self.on_complete,
    "error": self.on_error
})
```

### Requirements

`stream()` needs a running transport. If the connection is not started, has been stopped, or is reconnecting, it raises `HubConnectionError` and does not register the stream handler. The same rule applies to `send()` and `invoke()`.

```python
from signalrcore.hub.errors import HubConnectionError

try:
    hub_connection.stream("Counter", [10, 500]).subscribe({
        "next": on_next,
        "complete": on_complete,
        "error": on_error
    })
except HubConnectionError:
    print("Connection is not running")
```

### Example Callbacks

```python
def on_next(self, value):
    print(f"Received: {value}")

def on_complete(self, message):
    print("Stream complete")

def on_error(self, message):
    print(f"Stream error: {message}")
```

---

## Client-to-Server Streaming

Use a `Subject` to stream data from the client to the server:

```python
from signalrcore.subject import Subject

subject = Subject()

# Start the streaming invocation
hub_connection.send("UploadStream", subject)

# Send items during the stream
subject.next(str(iteration))

# Signal end of stream
subject.complete()
```

### Full Client Streaming Example

```python
from signalrcore.subject import Subject
import time

subject = Subject()
hub_connection.send("UploadStream", subject)

for i in range(10):
    subject.next(str(i))
    time.sleep(0.5)

subject.complete()
```

---

## AsyncIO Streaming

The asyncio connection supports both streaming directions. `stream()` is a coroutine and must be awaited; the subscription callbacks may be synchronous or coroutine functions.

### Async Server-to-Client Streaming

```python
import asyncio

received = []
finished = asyncio.Event()

async def on_next(item):
    received.append(item)

def on_complete(message):
    finished.set()

async def on_error(message):
    print(f"Stream error: {message}")
    finished.set()

stream = await hub.stream("Counter", [10, 500])

stream.subscribe({
    "next": on_next,
    "complete": on_complete,
    "error": on_error
})

await finished.wait()
```

Each callback is awaited when it returns an awaitable. Items that arrive before `subscribe()` is called are buffered and delivered in order once the callbacks are registered, so a fast stream does not lose its first item.

### Async Client-to-Server Streaming

Use `AIOSubject` instead of the thread-based `Subject`:

```python
from signalrcore.aio.subject import AIOSubject

subject = AIOSubject()

await hub.send("UploadStream", subject)

for i in range(10):
    await subject.next(str(i))

await subject.complete()
```

`AIOSubject` serializes sends with an `asyncio.Lock` and keeps the stream order. Its constructor accepts a lock timeout, for example `AIOSubject(timeout=10)`; a timeout raises the built-in `TimeoutError`. Passing the synchronous `Subject` to an AIO connection raises a `TypeError`.

### Full Async Streaming Example

```python
import asyncio
import logging

from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder
from signalrcore.aio.subject import AIOSubject


async def main():
    hub = AIOHubConnectionBuilder()\
        .with_url(
            "wss://localhost:5001/chatHub",
            options={"verify_ssl": False})\
        .configure_logging(logging.INFO)\
        .build()

    await hub.start()

    try:
        # Server-to-client stream.
        done = asyncio.Event()

        stream = await hub.stream("Counter", [5, 500])
        stream.subscribe({
            "next": lambda item: print("Received:", item),
            "complete": lambda message: done.set(),
            "error": lambda message: done.set()
        })

        await done.wait()

        # Client-to-server stream.
        subject = AIOSubject()
        await hub.send("UploadStream", subject)

        for i in range(5):
            await subject.next(f"chunk-{i}")

        await subject.complete()
    finally:
        await hub.stop()


asyncio.run(main())
```

See the [AsyncIO (AIO)](aio) page for transports, authentication, reconnection and timeout configuration.

---

## Notes

- Server-to-client streaming uses the `IAsyncEnumerable<T>` or `ChannelReader<T>` pattern on the .NET server side.
- Client-to-server streaming sends items incrementally until `subject.complete()` is called.
- More examples are available in the [tests folder](https://github.com/mandrewcito/signalrcore/tree/master/test/examples).
