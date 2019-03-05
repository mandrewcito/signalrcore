
import time
from signalrcore.hub_connection import HubConnection


def input_with_default(input_text, default_value):
    value = input(input_text.format(default_value))
    return default_value if value is None or value.strip() == "" else value


server_url = input_with_default('Enter your server url(default: {0}): ', "ws://localhost:57957/streamHub")

hub_connection = HubConnection(server_url)
hub_connection.build()
hub_connection.start()
time.sleep(10)
hub_connection.stream(
    "Counter",
    [10, 500],
    lambda x: print("next callback: ", x),
    lambda x: print("complete  callback", x),
    lambda x: print("error  callback", x))

message = None
while message != "exit()":
    message = input(">> ")

hub_connection.stop()
