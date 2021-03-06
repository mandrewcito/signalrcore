
import time
import sys
sys.path.append("./")
from signalrcore.hub_connection_builder import HubConnectionBuilder
import logging


def input_with_default(input_text, default_value):
    value = input(input_text.format(default_value))
    return default_value if value is None or value.strip() == "" else value


server_url = input_with_default('Enter your server url(default: {0}): ', "wss://localhost:5001/chatHub")

hub_connection = HubConnectionBuilder().with_url(server_url, options={"verify_ssl": False}) \
    .configure_logging(logging.DEBUG, socket_trace=True) \
    .build()
hub_connection.start()
time.sleep(10)

end = False


def bye(error, x):
    global end
    end = True
    if error:
        print("error {0}".format(x))
    else:
        print("complete! ")
    global hub_connection


hub_connection.stream(
    "Counter",
    [10, 500]).subscribe({
        "next": lambda x: print("next callback: ", x),
        "complete": lambda x: bye(False, x),
        "error": lambda x: bye(True, x)
    })

while not end:
    time.sleep(1)

hub_connection.stop()
