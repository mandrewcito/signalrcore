# SignalR core client
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg?logo=paypal&style=flat-square)](https://www.paypal.me/mandrewcito/1)
![Pypi](https://img.shields.io/pypi/v/signalrcore.svg)
[![Downloads](https://pepy.tech/badge/signalrcore/month)](https://pepy.tech/project/signalrcore/month)
[![Downloads](https://pepy.tech/badge/signalrcore)](https://pepy.tech/project/signalrcore)
![Issues](https://img.shields.io/github/issues/mandrewcito/signalrcore.svg)
![Open issues](https://img.shields.io/github/issues-raw/mandrewcito/signalrcore.svg)
![travis build](https://img.shields.io/travis/mandrewcito/signalrcore.svg)
![codecov.io](https://codecov.io/github/mandrewcito/signalrcore/coverage.svg?branch=master)

![logo alt](https://raw.githubusercontent.com/mandrewcito/signalrcore/master/docs/img/logo_temp.128.svg.png)


# Links 

* [Dev to posts with library examples and implementation](https://dev.to/mandrewcito/singlar-core-python-client-58e7)

* [Pypi](https://pypi.org/project/signalrcore/)

* [Wiki - This Doc](https://mandrewcito.github.io/signalrcore/)

# Develop

Test server will be avaiable in [here](https://github.com/mandrewcito/signalrcore-containertestservers) and docker compose is required.

```bash
git clone https://github.com/mandrewcito/signalrcore-containertestservers
cd signalrcore-containertestservers
docker-compose up
cd ../signalrcore
make tests
```

## Known Issues

Issues related with closing sockets are inherited from the websocket-client library. Due to these problems i can't update the library to versions higher than websocket-client 0.54.0. 
I'm working to solve it but for now its patched (Error number 1. Raises an exception, and then exception is treated for prevent errors). 
If I update the websocket library I fall into error number 2, on local machine I can't reproduce it but travis builds fail (sometimes and randomly :()
* [1. Closing socket error](https://github.com/slackapi/python-slackclient/issues/171)
* [2. Random errors closing socket](https://github.com/websocket-client/websocket-client/issues/449)

# A Tiny How To

## Connect to a server without auth

```python
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
## Connect to a server with auth

login_function must provide auth token

```python
hub_connection = HubConnectionBuilder()\
            .with_url(server_url,
            options={
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
### Unauthorized errors
A login function must provide an error controller if authorization fails. When connection starts, if authorization fails exception will be propagated.

```python
    def login(self):
        response = requests.post(
            self.login_url,
            json={
                "username": self.email,
                "password": self.password
                },verify=False)
        if response.status_code == 200:
            return response.json()["token"]
        raise requests.exceptions.ConnectionError()

    hub_connection.start()   # this code will raise  requests.exceptions.ConnectionError() if auth fails
```
## Configure logging

```python
HubConnectionBuilder()\
    .with_url(server_url,
    .configure_logging(logging.DEBUG)
    ...
```
## Configure socket trace
```python 
HubConnectionBuilder()\
    .with_url(server_url,
    .configure_logging(logging.DEBUG, socket_trace=True) 
    ... 
 ```
## Configure your own handler
```python
 import logging
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
hub_connection = HubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False}) \
    .configure_logging(logging.DEBUG, socket_trace=True, handler=handler)
    ...
 ```
## Configuring reconnection
After reaching max_attempts an exeption will be thrown and on_disconnect event will be fired.
```python
hub_connection = HubConnectionBuilder()\
    .with_url(server_url)\
    ...
    .build()
```
## Configuring additional headers
```python
hub_connection = HubConnectionBuilder()\
            .with_url(server_url,
            options={
                "headers": {
                    "mycustomheader": "mycustomheadervalue"
                }
            })
            ...
            .build()
```
## Configuring additional querystring parameters
```python
server_url ="http.... /?myquerystringparam=134&foo=bar"
connection = HubConnectionBuilder()\
            .with_url(server_url,
            options={
            })\
            .build()
```
## Congfiguring skip negotiation
```python
hub_connection = HubConnectionBuilder() \
        .with_url("ws://"+server_url, options={
            "verify_ssl": False,
            "skip_negotiation": False,
            "headers": {
            }
        }) \
        .configure_logging(logging.DEBUG, socket_trace=True, handler=handler) \
        .build()

```
## Configuring ping(keep alive)

keep_alive_interval sets the seconds of ping message

```python
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
## Configuring logging
```python
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

## Configure messagepack

```python
from signalrcore.protocol.messagepack_protocol import MessagePackHubProtocol

HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
                ... 
            .with_hub_protocol(MessagePackHubProtocol())\
                ...
            .build()
```
## Events

### On Connect / On Disconnect
on_open - fires when connection is opened and ready to send messages
on_close - fires when connection is closed
```python
hub_connection.on_open(lambda: print("connection opened and handshake received ready to send messages"))
hub_connection.on_close(lambda: print("connection closed"))

```
### On Hub Error (Hub Exceptions ...)
```
hub_connection.on_error(lambda data: print(f"An exception was thrown closed{data.error}"))
```
### Register an operation 
ReceiveMessage - signalr method
print - function that has as parameters args of signalr method
```python
hub_connection.on("ReceiveMessage", print)
```
## Sending messages
SendMessage - signalr method
username, message - parameters of signalrmethod
```python
    hub_connection.send("SendMessage", [username, message])
```

## Sending messages with callback
SendMessage - signalr method
username, message - parameters of signalrmethod
```python
    send_callback_received = threading.Lock()
    send_callback_received.acquire()
    self.connection.send(
        "SendMessage", # Method
        [self.username, self.message], # Params
        lambda m: send_callback_received.release()) # Callback
    if not send_callback_received.acquire(timeout=1):
        raise ValueError("CALLBACK NOT RECEIVED")
```

## Requesting streaming (Server to client)
```python
hub_connection.stream(
            "Counter",
            [len(self.items), 500]).subscribe({
                "next": self.on_next,
                "complete": self.on_complete,
                "error": self.on_error
            })
```
## Client side Streaming
```python
from signalrcore.subject import  Subject

subject = Subject()

# Start Streaming
hub_connection.send("UploadStream", subject)

# Each iteration
subject.next(str(iteration))

# End streaming
subject.complete()
```

# Full Examples

Examples will be avaiable [here](https://github.com/mandrewcito/signalrcore/tree/master/test/examples)
It were developed using package from [aspnet core - SignalRChat](https://codeload.github.com/aspnet/Docs/zip/master) 

## Chat example
A mini example could be something like this:

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
    .with_url(server_url, options={"verify_ssl": False}) \
    .configure_logging(logging.DEBUG, socket_trace=True, handler=handler) \
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

# Do login

while message != "exit()":
    message = input(">> ")
    if message is not None and message != "" and message != "exit()":
        hub_connection.send("SendMessage", [username, message])

hub_connection.stop()

sys.exit(0)

```
