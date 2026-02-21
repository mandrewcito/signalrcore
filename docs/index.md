---
layout: default
title: Home
nav_order: 1
description: "SignalR Core Python Client — full-featured Python client for ASP.NET Core SignalR"
permalink: /
---

# SignalR Core Python Client
{: .fs-9 }

A complete Python client for ASP.NET Core SignalR — supporting all transports, encodings, authentication, and reconnection strategies.
{: .fs-6 .fw-300 }

[Get Started](getting-started){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[View on GitHub](https://github.com/mandrewcito/signalrcore){: .btn .fs-5 .mb-4 .mb-md-0 }

---

![SignalR Core Python Client](img/logo_temp.128.svg.png)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg?logo=paypal&style=flat-square)](https://www.paypal.me/mandrewcito/1)
![PyPI](https://img.shields.io/pypi/v/signalrcore.svg)
[![Downloads](https://pepy.tech/badge/signalrcore/month)](https://pepy.tech/project/signalrcore/month)
[![Downloads](https://pepy.tech/badge/signalrcore)](https://pepy.tech/project/signalrcore)
![Issues](https://img.shields.io/github/issues/mandrewcito/signalrcore.svg)
![codecov](https://codecov.io/github/mandrewcito/signalrcore/coverage.svg?branch=master)

---

## Features (V1.0.0 "poluca")

| Feature | Details |
|---------|---------|
| **Transports** | WebSockets, Server-Sent Events, Long Polling |
| **Encodings** | JSON (text), MessagePack (binary) |
| **Authentication** | Access token factory, custom headers |
| **Reconnection** | Raw interval, exponential backoff strategies |
| **SSL/TLS** | Custom SSL context passthrough |
| **Streaming** | Server-to-client and client-to-server streaming |
| **AsyncIO** | Async/await support via `AIOHubConnectionBuilder` |

## Quick Example

```python
import logging
from signalrcore.hub_connection_builder import HubConnectionBuilder

hub_connection = HubConnectionBuilder()\
    .with_url("wss://localhost:44376/chatHub")\
    .configure_logging(logging.DEBUG)\
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    }).build()

hub_connection.on_open(lambda: print("Connected!"))
hub_connection.on_close(lambda: print("Disconnected"))
hub_connection.on("ReceiveMessage", print)

hub_connection.start()
hub_connection.send("SendMessage", ["username", "Hello!"])
hub_connection.stop()
```

## Upcoming Changes

- Enhanced AsyncIO transport layer and callbacks
- Test suite split into integration and unit tests
- Ack/Sequence implementation
- Azure managed solution for testing

## Links

- [Dev.to posts with library examples](https://dev.to/mandrewcito/singlar-core-python-client-58e7)
- [PyPI Package](https://pypi.org/project/signalrcore/)
- [ASP.NET Core SignalR docs](https://github.com/dotnet/aspnetcore/tree/main/src/SignalR/docs)
- [Issue Tracker](https://github.com/mandrewcito/signalrcore/issues)
