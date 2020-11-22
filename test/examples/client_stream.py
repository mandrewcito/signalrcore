
import time
import sys
sys.path.append("./")
import logging
from signalrcore.hub_connection_builder import HubConnectionBuilder
from signalrcore.subject import Subject


def input_with_default(input_text, default_value):
    value = input(input_text.format(default_value))
    return default_value if value is None or value.strip() == "" else value


server_url = input_with_default('Enter your server url(default: {0}): ', "wss://localhost:5001/chatHub")

hub_connection = HubConnectionBuilder()\
    .with_url(server_url, options={"verify_ssl": False}) \
    .configure_logging(logging.DEBUG) \
    .with_automatic_reconnect({
            "type": "interval",
            "keep_alive_interval": 10,
            "intervals": [1, 3, 5, 6, 7, 87, 3]
        })\
    .build()
hub_connection.start()
time.sleep(10)


def bye(error, x):
    if error:
        print("error {0}".format(x))
    else:
        print("complete! ")
    global hub_connection
    hub_connection.stop()
    sys.exit(0)


iteration = 0
subject = Subject()


def interval_handle():
    global iteration
    iteration += 1
    subject.next(str(iteration))
    if iteration == 10:
        subject.complete()


hub_connection.send("UploadStream", subject)

while iteration != 10:
    interval_handle()
    time.sleep(0.5)

