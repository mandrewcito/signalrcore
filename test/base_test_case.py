import unittest
import logging
import time
from signalrcore.hub_connection_builder import HubConnectionBuilder

class Urls:
    server_url_no_ssl = "ws://localhost:5000/chatHub"
    server_url_ssl = "wss://localhost:5001/chatHub"
    server_url_no_ssl_auth = "ws://localhost:5000/authHub"
    server_url_ssl_auth = "wss://localhost:5001/authHub"
    login_url_ssl =  "https://localhost:5001/users/authenticate"
    login_url_no_ssl =  "http://localhost:5000/users/authenticate"