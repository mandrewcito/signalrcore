import requests
import sys
import logging
sys.path.append("./")
from signalrcore.hub_connection_builder import HubConnectionBuilder


def input_with_default(input_text, default_value):
    value = input(input_text.format(default_value))
    return default_value if value is None or value.strip() == "" else value


def signalr_core_example_login(url, user, username_password):
    response = requests.post(url, json={"username": user, "password": username_password}, verify=False)
    return response.json()["token"]


login_url = input_with_default('Enter your server login url({0}):', "https://localhost:5001/users/authenticate")
server_url = input_with_default('Enter your server url(default: {0}): ', "wss://localhost:5001/authHub")
username = input_with_default('Enter your username (default: {0}): ', "test")
password = input_with_default('Enter your password (default: {0}): ', "test")

hub_connection = HubConnectionBuilder()\
    .configure_logging(logging_level=logging.DEBUG)\
    .with_url(server_url, options={
        "access_token_factory": lambda: signalr_core_example_login(login_url, username, password),
        "verify_ssl": False
    }).with_automatic_reconnect({
        "type": "interval",
        "keep_alive_interval": 10,
        "intervals": [1, 3, 5, 6, 7, 87, 3]
    })\
    .build()

hub_connection.on_open(lambda: print("connection opened and handshake received ready to send messages"))
hub_connection.on_close(lambda: print("connection closed"))

hub_connection.on("ReceiveSystemMessage", print)
hub_connection.on("ReceiveChatMessage", print)
hub_connection.on("ReceiveDirectMessage", print)

hub_connection.start()
message = None
while message != "exit()":
    message = input(">> ")
    if message is not None and message != "" and message != "exit()":
        hub_connection.send("Send", [message])
hub_connection.stop()
