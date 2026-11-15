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
| `TimeoutError` | builtin | An AIO connection stage, state wait or stream lock does not complete in time |

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

AIO `start()` waits for the transport to finish the handshake for at most `AIO_CONNECTION_TIMEOUT` seconds (30 by default). Negotiation and the transport connection have their own bounds (`AIO_NEGOTIATE_TIMEOUT` and `AIO_CONNECT_TIMEOUT`, 30 seconds each). If a stage does not complete, `TimeoutError` is raised. `stop()` bounds client shutdown with `AIO_CLOSE_TIMEOUT` (10 seconds by default).

```python
from signalrcore.transport.base_transport import TransportState

await hub.wait_until_state(TransportState.connected, timeout=10)
```

`wait_until_state()` accepts an optional timeout; without one it waits indefinitely. `stop()` is safe to call before `start()`: a missing transport counts as disconnected, so the call returns immediately instead of waiting for a state that can never be reached.

---

## Server-Side Hub Errors

Errors reported by the server during an invocation are delivered to the `on_error` handler instead of being raised by the call:

```python
hub_connection.on_error(lambda data: print(f"Hub error: {data.error}"))
```
