import requests
from signalrcore.hub_connection_builder import HubConnectionBuilder


def print_message(x):
    print x

def input_with_default(input_text, default_value):
    value = raw_input (input_text.format(default_value))
    return default_value if value is None or value.strip() == "" else value


def signalr_core_example_login(url, user, username_password):
    response = requests.post(url, data={"email": user, "password": username_password})
    return response.json()["token"]


login_url = input_with_default('Enter your server login url({0}):', "http://localhost:50746/account/token")
server_url = input_with_default('Enter your server url(default: {0}): ', "ws://localhost:50746/hubs/chat")
username = input_with_default('Enter your username (default: {0}): ', "mandrewcito@mandrewcito.com")
password = input_with_default('Enter your password (default: {0}): ', "Abc123.--123?")

hub_connection = HubConnectionBuilder()\
    .with_url(server_url, options={
        "access_token_factory": lambda: signalr_core_example_login(login_url, username, password)
    }).with_automatic_reconnect({
        "type": "interval",
        "keep_alive_interval": 10,
        "intervals": [1, 3, 5, 6, 7, 87, 3]
    })\
    .build()

hub_connection.on("ReceiveSystemMessage", print_message)
hub_connection.on("ReceiveChatMessage", print_message)
hub_connection.on("ReceiveDirectMessage", print_message)
hub_connection.start()
message = None
while message != "exit()":
    message = raw_input(">> ")
    if message is not None and message is not "" and message is not "exit()":
        hub_connection.send("Send", [message])
hub_connection.stop()
