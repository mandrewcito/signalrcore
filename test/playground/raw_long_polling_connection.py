import time
import requests
import json
import base64
import random
import sys
import threading

sys.path.append("./")

BASE_URL = "https://localhost:5001/chathub"
VERIFY_SSL = False
RUNNING = False
VERSION = 1


def negotiate(version):
    url = f"{BASE_URL}/negotiate"
    params = {
        "negotiateVersion": version
    }

    response = requests.post(
        url,
        params=params,
        verify=VERIFY_SSL
    )

    status_code, data = response.status_code, response.content

    print(
        f"NEGOTIATE {status_code}:",
        json.dumps(data.decode("utf-8"), indent=2))

    return response.json()


def long_polling_loop(ID):
    global RUNNING

    url = f"{BASE_URL}"

    params = {
        "id": ID,
        "transport": "longPolling"
    }

    while RUNNING:
        try:
            response = requests.get(
                url=url,
                headers={
                    },
                params=params,
                verify=VERIFY_SSL
            )

            status_code, data = response.status_code, response.content

            if status_code == 404:
                print("LP:: not found . . . . . ")
                time.sleep(10)
        except requests.exceptions.Timeout:
            print("LP::Timeout, reconnect ...")
        except Exception as e:
            print(e)
            time.sleep(20)
        finally:
            if data is not None:
                print(f"LP:: {data}")


def send_message(body: dict) -> requests.Response:
    return requests.post(
                url=BASE_URL,
                verify=VERIFY_SSL,
                params={
                    "id": ID
                },
                data=json.dumps(body)
                .encode("utf-8") + chr(0x1E).encode("utf-8")
                )


if __name__ == "__main__":
    negotiate_data = negotiate(VERSION)

    version = negotiate_data["negotiateVersion"]
    connection_token = negotiate_data.get("connectionToken", None)
    connection_id = negotiate_data.get("connectionId", None)

    print(f"Token: {connection_token}")
    print(f"Connection ID: {connection_id}")

    ID = connection_token if version == 1 else connection_id

    th = threading.Thread(
        args=(ID,),
        target=long_polling_loop

    )

    RUNNING = True
    th.start()

    msg = ""

    response = send_message(
        {
            "protocol": "json",
            "version": VERSION
        }
    )

    print(response)

    while msg != "exit":
        msg = input("> ")
        if msg != exit and msg is not None and len(msg) > 0:
            key = base64.b64encode(
                f"{random.randint(1, 100)}".encode()).decode()

            response = send_message({
                    "type": 1,
                    "invocationId": key,
                    "target": "SendMessage",
                    "arguments": [
                        "mandrewcito",
                        msg
                        ]
                    })

            status_code, data = response.status_code, response.content

            print(status_code, data)
    th.join()
    sys.exit(0)
