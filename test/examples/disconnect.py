import threading
import logging
import sys
import time

sys.path.append("./")

from signalrcore.hub_connection_builder\
    import HubConnectionBuilder  # noqa: E402

connection = HubConnectionBuilder()\
    .with_url("wss://localhost:5001/chathub", options={"verify_ssl": False})\
    .configure_logging(logging.DEBUG)\
    .build()

_lock = threading.Lock()


def release():
    global _lock
    _lock.release()


connection.on_open(release)
connection.on_close(release)

connection.on("ReceiveMessage", release)

(_lock.acquire(timeout=30))  # Released on open

connection.start()

(_lock.acquire(timeout=30))  # Released on ReOpen

connection.send("DisconnectMe", [])

time.sleep(30)

(_lock.acquire(timeout=30))

connection.send("DisconnectMe", [])
