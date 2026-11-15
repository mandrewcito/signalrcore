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

The `AIOHubConnectionBuilder` provides an `async`/`await` compatible connection for use in asyncio-based applications. This is a minimal implementation and will be expanded in future versions.

---

## Creating a Connection

```python
from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder

builder = AIOHubConnectionBuilder()\
    .with_url(server_url, options=options)\
    .configure_logging(logging.DEBUG, socket_trace=True)\
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    })

hub = builder.build()
```

---

## Starting and Stopping

```python
await hub.start()

# ... use the connection ...

await hub.stop()
```

`start()` and `stop()` wait for the transport to reach the `connected`/`disconnected` state. The wait is bounded by `AIO_CONNECTION_TIMEOUT` (30 seconds by default); if the state is never reached, `TimeoutError` is raised instead of hanging. Exceptions raised by the underlying start/stop are propagated to the caller.

`stop()` is safe to call before `start()` — a missing transport counts as disconnected and the call returns immediately.

---

## Sending Messages

```python
await hub.send("SendMessage", [username, message])
```

---

## Full AIO Example

```python
import asyncio
import logging
from signalrcore.aio.aio_hub_connection_builder import AIOHubConnectionBuilder


async def main():
    server_url = "wss://localhost:44376/chatHub"
    options = {"verify_ssl": False}

    hub = AIOHubConnectionBuilder()\
        .with_url(server_url, options=options)\
        .configure_logging(logging.DEBUG, socket_trace=True)\
        .with_automatic_reconnect({
            "type": "raw",
            "keep_alive_interval": 10,
            "reconnect_interval": 5,
            "max_attempts": 5
        }).build()

    hub.on_open(lambda: print("Connected!"))
    hub.on_close(lambda: print("Disconnected"))
    hub.on("ReceiveMessage", print)

    await hub.start()
    await hub.send("SendMessage", ["user", "Hello from async!"])
    await hub.stop()


asyncio.run(main())
```

---

## Notes

- The AIO implementation is currently minimal. Upcoming versions will include full async transport layer support and async callbacks.
- For authentication, pass an `access_token_factory` in the options dictionary.
- The same configuration options (transport, SSL context, headers) available in the sync builder are supported.
