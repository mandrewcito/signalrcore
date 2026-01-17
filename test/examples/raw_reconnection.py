import threading
import logging
import sys
import time

sys.path.append("./")

from signalrcore.hub_connection_builder\
    import HubConnectionBuilder  # noqa: E402

connection = HubConnectionBuilder()\
    .with_url("wss://localhost:5001/chathub", options={"verify_ssl": False})\
    .with_automatic_reconnect(
        {
            "type": "raw",
            "keep_alive_interval": 15,
            "reconnect_interval": 30,
            "max_attempts": 5})\
    .configure_logging(logging.DEBUG)\
    .build()

_lock = threading.Lock()


def on_open():
    release("on_open")


def on_close():
    release("on_close")


def on_reconnect():
    release("on_reconnect")


def release(msg):
    global _lock
    _lock.release()
    print(msg)


connection.on_open(on_open)

connection.on("ReceiveMessage", print)

assert _lock.acquire(timeout=30), "Failed, lock already acquired"

connection.start()

assert _lock.acquire(timeout=30), "Failed, not released on_open"

connection.on_open(lambda: print("on_open callback will not been fired again"))
connection.on_reconnect(on_reconnect)


connection.send("DisconnectMe", [])

time.sleep(15)

assert _lock.acquire(timeout=30), "Failed, not released on_reconnect"

connection.on_close(on_close)
connection.stop()

del _lock
