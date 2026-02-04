import sys
import time
import random
import base64
import json
import logging
sys.path.append("./")
from signalrcore.transport.websockets.websocket_client import WebSocketClient  # noqa E402
from signalrcore.transport.sockets.utils import create_ssl_context  # noqa E402s

logging.basicConfig(level=logging.DEBUG)


def on_open():
    print("socket opened mi rey")


def on_error(ex: Exception = None):
    print("socket errored mi rey")
    if ex:
        print(ex)


def on_close():
    print("socket closed mi rey")


app = WebSocketClient(
    url="https://localhost:5001/chathub",
    connection_id=None,
    enable_trace=False,
    headers={},
    proxies={},
    ssl_context=create_ssl_context(False),
    on_open=on_open,
    on_error=on_error,
    on_close=on_close,
    on_message=print)

app.connect()

time.sleep(2)

msg = json.dumps({"protocol": "json", "version": 1})
app.send(msg + str(chr(0x1E)))

time.sleep(2)

while msg != "exit":
    msg = input("> ")
    if msg != exit and msg is not None and len(msg) > 0:
        key = base64.b64encode(f"{random.randint(1, 100)}".encode()).decode()
        app.send(json.dumps({
            "type": 1,
            "invocationId": key,
            "target": "SendMessage",
            "arguments": [
                "mandrewcito",
                msg
            ]
        }))

app.close()

print("END SCRIPT")
