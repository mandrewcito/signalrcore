---
layout: default
title: Configuration
nav_order: 3
---

# Configuration
{: .no_toc }

## Table of Contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Logging

```python
HubConnectionBuilder()\
    .with_url(server_url)\
    .configure_logging(logging.DEBUG)\
    ...
```

### Socket Trace

```python
HubConnectionBuilder()\
    .with_url(server_url)\
    .configure_logging(logging.DEBUG, socket_trace=True)\
    ...
```

### Custom Handler

```python
import logging

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)

HubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False})\
    .configure_logging(logging.DEBUG, socket_trace=True, handler=handler)\
    ...
```

---

## Reconnection

After reaching `max_attempts`, an exception is thrown and the `on_close` event fires.

### Raw Interval Strategy

Reconnects at a fixed interval:

```python
hub_connection = HubConnectionBuilder()\
    .with_url(server_url)\
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    }).build()
```

### Interval Backoff Strategy

Reconnects using a list of increasing intervals:

```python
hub_connection = HubConnectionBuilder()\
    .with_url(server_url)\
    .with_automatic_reconnect({
        "type": "interval",
        "keep_alive_interval": 10,
        "intervals": [1, 3, 5, 6, 7, 87, 3]
    }).build()
```

### Keep-Alive (Ping)

`keep_alive_interval` sets the number of seconds between ping messages sent to the server.

---

## Headers

```python
hub_connection = HubConnectionBuilder()\
    .with_url(server_url, options={
        "headers": {
            "mycustomheader": "mycustomheadervalue"
        }
    })\
    .build()
```

---

## Query String Parameters

Pass parameters directly in the URL:

```python
server_url = "http://.../?myQueryStringParam=134&foo=bar"

connection = HubConnectionBuilder()\
    .with_url(server_url)\
    .build()
```

---

## Skip Negotiation

```python
hub_connection = HubConnectionBuilder()\
    .with_url("ws://" + server_url, options={
        "verify_ssl": False,
        "skip_negotiation": False,
        "headers": {}
    })\
    .configure_logging(logging.DEBUG, socket_trace=True, handler=handler)\
    .build()
```

---

## Transport

### WebSockets (default)

Used by default — no explicit configuration needed.

```python
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.transport.websockets.websocket_transport import HttpTransportType

HubConnectionBuilder()\
    .with_url(server_url, options={
        "transport": HttpTransportType.web_sockets
    })\
    .configure_logging(logging.ERROR)\
    .build()
```

### Server-Sent Events

```python
HubConnectionBuilder()\
    .with_url(server_url, options={
        "transport": HttpTransportType.server_sent_events
    })\
    .configure_logging(logging.ERROR)\
    .build()
```

### Long Polling

```python
HubConnectionBuilder()\
    .with_url(server_url, options={
        "transport": HttpTransportType.long_polling
    })\
    .configure_logging(logging.ERROR)\
    .build()
```

---

## MessagePack Encoding

By default, JSON encoding is used. To switch to binary MessagePack:

```python
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol

HubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False})\
    .with_hub_protocol(MessagePackHubProtocol())\
    .build()
```

---

## Custom SSL Context

Pass a custom SSL context to all requests and socket connections:

```python
import ssl

MY_CA_FILE_PATH = "ca.crt"
context = ssl.create_default_context(cafile=MY_CA_FILE_PATH)

options = {"ssl_context": context}

connection = HubConnectionBuilder()\
    .with_url(server_url, options=options)\
    .configure_logging(logging.INFO, socket_trace=True)\
    .build()
```

For full certificate setup instructions, see the [Custom Client Certificates](articles/custom-client-cert) article.
