import threading
import logging
import sys
import time

sys.path.append("./")

from signalrcore.hub_connection_builder import HubConnectionBuilder

connection = HubConnectionBuilder()\
    .with_url("wss://localhost:5001/chathub", options={"verify_ssl": False})\
    .configure_logging(logging.ERROR)\
    .build()

_lock = threading.Lock()

connection.on_open(lambda: _lock.release())
connection.on_close(lambda: _lock.release())

connection.on("ReceiveMessage", lambda _: _lock.release())

(_lock.acquire(timeout=30))  # Released on open

connection.start()

(_lock.acquire(timeout=30))  # Released on ReOpen

connection.send("DisconnectMe", [])

time.sleep(30)

(_lock.acquire(timeout=30))

connection.send("DisconnectMe", [])
