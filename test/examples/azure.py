import logging
import sys
import requests

sys.path.append("./")
from signalrcore.hub_connection_builder import HubConnectionBuilder  # noqa: E402, E501


def input_with_default(input_text, default_value):
    value = input(input_text.format(default_value))
    return default_value if value is None or value.strip() == "" else value


AZURE_DEFAULT_URL = "http://localhost:7071/api/"

server_url = input_with_default(
    'Enter your server url(default: {0}): ',
    AZURE_DEFAULT_URL)

username = input_with_default(
    'Enter your username (default: {0}): ', "mandrewcito")

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)


hub_connection = HubConnectionBuilder() \
        .with_url(server_url, options={
            "verify_ssl": False,
            "skip_negotiation": False,
            "headers": {
            }
        }) \
        .configure_logging(logging.DEBUG, socket_trace=True, handler=handler) \
        .build()

hub_connection.on_open(lambda: print(
    "connection opened and handshake received ready to send messages"))
hub_connection.on_close(lambda: print("connection closed"))

hub_connection.on("newMessage", print)
hub_connection.start()
message = None

# Do login

while message != "exit()":
    message = input(">> ")
    if message is not None and message != "" and message != "exit()":
        # hub_connection.send("sendMessage", [username, message])
        requests.post(
            f"{server_url}messages",
            json={"sender": username, "text": message})

hub_connection.stop()

sys.exit(0)
