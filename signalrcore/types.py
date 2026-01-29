import enum


class HttpTransportType(enum.Enum):
    web_sockets = "WebSockets"
    server_sent_events = "ServerSentEvents"
    long_polling = "LongPolling"


class HubProtocolEncoding(enum.Enum):
    text = "Text"
    binary = "Binary"


RECORD_SEPARATOR = chr(0x1E)
