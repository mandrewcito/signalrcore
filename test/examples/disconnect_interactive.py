import threading
import logging
import sys
import time

sys.path.append("./")

from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.hub.errors import HubConnectionError
connection = HubConnectionBuilder()\
    .with_url("wss://localhost:5001/chathub", options={"verify_ssl": False})\
    .configure_logging(logging.DEBUG)\
    .with_automatic_reconnect(
        {
            "type": "raw",
            "keep_alive_interval": 10,
            "reconnect_interval": 5,
            "max_attempts": None
        })\
    .build()

_lock = threading.Lock()

connection.on_open(lambda: _lock.release())
connection.on_close(lambda: _lock.release())

#connection.on("ReceiveMessage", lambda _: _lock.release())

(_lock.acquire(timeout=5))  # Released on open

connection.start()

(_lock.acquire(timeout=5))  # Released on ReOpen

#connection.send("DisconnectMe", [])

time.sleep(5)

message = ""
while message != "exit":
    message = input("-> ")
    try:
        connection.send("SendMessage", ["usr", message])
    except HubConnectionError:
        pass

_lock.release()

connection.stop()
    
(_lock.acquire(timeout=30))

