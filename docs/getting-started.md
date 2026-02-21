---
layout: default
title: Getting Started
nav_order: 2
---

# Getting Started
{: .no_toc }

## Table of Contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## Installation

```bash
pip install signalrcore
```

**Requirements:**
- Python >= 3.9
- For MessagePack encoding: `msgpack >= 1.1.2` (installed automatically)

---

## Basic Connection

### Without Authentication

```python
import logging
from signalrcore.hub_connection_builder import HubConnectionBuilder

hub_connection = HubConnectionBuilder()\
    .with_url(server_url)\
    .configure_logging(logging.DEBUG)\
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    }).build()
```

### With Authentication

The `access_token_factory` must be a callable that returns the auth token:

```python
hub_connection = HubConnectionBuilder()\
    .with_url(server_url, options={
        "access_token_factory": login_function,
        "headers": {
            "mycustomheader": "mycustomheadervalue"
        }
    })\
    .configure_logging(logging.DEBUG)\
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    }).build()
```

If authorization fails, the exception is propagated when calling `hub_connection.start()`.

```python
def login(self):
    response = requests.post(
        self.login_url,
        json={"username": self.email, "password": self.password},
        verify=False
    )
    if response.status_code == 200:
        return response.json()["token"]
    raise requests.exceptions.ConnectionError()

hub_connection.start()  # raises ConnectionError if auth fails
```

---

## Events

### Connection Lifecycle

```python
hub_connection.on_open(lambda: print("connection opened and ready to send messages"))
hub_connection.on_close(lambda: print("connection closed"))
```

### Hub Errors

```python
hub_connection.on_error(lambda data: print(f"An exception was thrown: {data.error}"))
```

### Registering Hub Methods

```python
# "ReceiveMessage" is the SignalR method name
# print is called with the method's arguments
hub_connection.on("ReceiveMessage", print)
```

---

## Sending Messages

```python
# SendMessage - SignalR method name
# [username, message] - method parameters
hub_connection.send("SendMessage", [username, message])
```

### With Callback

```python
import threading

send_callback_received = threading.Lock()
send_callback_received.acquire()

hub_connection.send(
    "SendMessage",
    [username, message],
    lambda m: send_callback_received.release()  # Callback on completion
)

if not send_callback_received.acquire(timeout=1):
    raise ValueError("CALLBACK NOT RECEIVED")
```

---

## Development Setup

Requirements:
- Python >= 3.9
- virtualenv
- pip
- docker
- docker compose

The test environment requires a SignalR Core server available at [signalrcore-containertestservers](https://github.com/mandrewcito/signalrcore-containertestservers).

```bash
git clone https://github.com/mandrewcito/signalrcore
cd signalrcore
make dev-install

git clone https://github.com/mandrewcito/signalrcore-containertestservers
cd signalrcore-containertestservers
docker compose up

cd ../signalrcore
make pytest-cov
```

---

## Full Chat Example

```python
import logging
import sys
from signalrcore.hub_connection_builder import HubConnectionBuilder


def input_with_default(input_text, default_value):
    value = input(input_text.format(default_value))
    return default_value if value is None or value.strip() == "" else value


server_url = input_with_default('Enter your server url(default: {0}): ', "wss://localhost:44376/chatHub")
username = input_with_default('Enter your username (default: {0}): ', "mandrewcito")

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)

hub_connection = HubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False})\
    .configure_logging(logging.DEBUG, socket_trace=True, handler=handler)\
    .with_automatic_reconnect({
        "type": "interval",
        "keep_alive_interval": 10,
        "intervals": [1, 3, 5, 6, 7, 87, 3]
    }).build()

hub_connection.on_open(lambda: print("connection opened and handshake received ready to send messages"))
hub_connection.on_close(lambda: print("connection closed"))
hub_connection.on("ReceiveMessage", print)

hub_connection.start()
message = None

while message != "exit()":
    message = input(">> ")
    if message is not None and message != "" and message != "exit()":
        hub_connection.send("SendMessage", [username, message])

hub_connection.stop()
sys.exit(0)
```

More examples are available in the [tests folder](https://github.com/mandrewcito/signalrcore/tree/master/test/examples).
