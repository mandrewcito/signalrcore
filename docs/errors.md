---
layout: default
title: Errors
nav_order: 6
---

# Errors
{: .no_toc }

## Table of Contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Exception Types

| Exception | Base class | Raised when |
|-----------|------------|-------------|
| `HubConnectionError` | `ValueError` | `send()`, `invoke()` or `stream()` is called without a running transport |
| `HubError` | `OSError` | Negotiation fails with a non-200 status or an invalid body, or the server reports a hub error |
| `UnAuthorizedHubError` | `HubError` | Negotiation returns HTTP 401 |
| `TimeoutError` | builtin | An AIO `start()`/`stop()` wait does not reach the expected state in time |

Import them from `signalrcore.hub.errors`:

```python
from signalrcore.hub.errors import (
    HubConnectionError,
    HubError,
    UnAuthorizedHubError,
)
```

---

## Connection Readiness

`send()`, `invoke()` and `stream()` require an open transport. Calling them before `start()`, after `stop()`, or while a reconnect is in progress raises `HubConnectionError`. No callback or stream handler is registered, so nothing is leaked in `stream_handlers`.

```python
try:
    hub_connection.send("SendMessage", ["hello"])
except HubConnectionError:
    print("Connection is not running")
```

---

## Negotiation Errors

The negotiate response status is checked before its body is parsed:

- `401` → `UnAuthorizedHubError`
- any other non-200 status → `HubError` carrying the status code
- `200` with a body that is not a JSON object → `HubError`

```python
from signalrcore.hub.errors import HubError, UnAuthorizedHubError

try:
    hub_connection.start()
except UnAuthorizedHubError:
    print("Check the access token")
except HubError as error:
    print(f"Negotiation failed: {error}")
```

---

## Async Connection Timeouts

AIO `start()` and `stop()` wait for the transport to reach the requested state for at most `AIO_CONNECTION_TIMEOUT` seconds (30 by default). If the state is not reached, `TimeoutError` is raised and the background state waiter is cancelled.

```python
from signalrcore.aio.hub import aio_base_hub_connection

aio_base_hub_connection.AIO_CONNECTION_TIMEOUT = 10

await hub.start()
```

`stop()` is safe to call before `start()`: a missing transport counts as disconnected, so the call returns immediately instead of waiting for a state that can never be reached.

---

## Server-Side Hub Errors

Errors reported by the server during an invocation are delivered to the `on_error` handler instead of being raised by the call:

```python
hub_connection.on_error(lambda data: print(f"Hub error: {data.error}"))
```
