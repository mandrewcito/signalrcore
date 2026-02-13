import ssl
from .hub.base_hub_connection import BaseHubConnection
from .hub.auth_hub_connection import AuthHubConnection
from .transport.reconnection import \
    IntervalReconnectionHandler, RawReconnectionHandler, ReconnectionType
from .helpers import Helpers
from .types import HttpTransportType, HubProtocolEncoding
from .protocol.protocol_factory import BaseHubProtocol
from .transport.sockets.utils import create_ssl_context


class HubConnectionBuilder(object):
    """
    Hub connection class, manages handshake and messaging

    Args:
        hub_url: SignalR core url

    Raises:
        HubConnectionError: Raises an Exception if url is empty or None
    """

    def __init__(self):
        self.hub_url = None

        self.options = {
            "access_token_factory": None
        }

        self.headers = dict()

        self.has_auth_configured = None

        self.protocol: BaseHubProtocol = None
        self.preferred_protocol = None
        self.preferred_transport = None

        self.reconnection_handler = None
        self.keep_alive_interval = 15

        self.ssl_context = ssl.create_default_context()
        self.enable_trace = False  # socket trace
        self.skip_negotiation = False  # By default do not skip negotiation
        self.proxies = dict()
        self.logger = Helpers.get_logger()

    def with_url(
            self,
            hub_url: str,
            options: dict = None):
        """Configure the hub url and options like negotiation and auth function

        def login(self):
            response = requests.post(
                self.login_url,
                json={
                    "username": self.email,
                    "password": self.password
                    },verify=False)
            return response.json()["token"]

        self.connection = HubConnectionBuilder()\
            .with_url(self.server_url,
            options={
                "verify_ssl": False,
                "access_token_factory": self.login,
                "headers": {
                    "mycustomheader": "mycustomheadervalue"
                }
            })\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            }).build()

        Args:
            hub_url (string): Hub URL
            options ([dict], optional): [description]. Defaults to None.

        Raises:
            ValueError: If url is invalid
            TypeError: If options are not a dict or auth function
                is not callable

        Returns:
            [HubConnectionBuilder]: configured connection
        """
        if hub_url is None or hub_url.strip() == "":
            raise ValueError("hub_url must be a valid url.")

        if options is not None and type(options) is not dict:
            raise TypeError(
                "options must be a dict {0}.".format(self.options))

        if options is not None:
            self.has_auth_configured = \
                "access_token_factory" in options.keys()\
                and callable(options["access_token_factory"])

            self.skip_negotiation = "skip_negotiation" in options.keys()\
                and options["skip_negotiation"]

            if "transport" in options.keys():
                transport = options.get("transport")
                if type(transport) is not HttpTransportType:
                    raise TypeError(
                        f"transport types:  {HttpTransportType}")
                self.preferred_transport = transport

            if "verify_ssl" in options.keys()\
                    and "ssl_context" in options.keys():
                raise ValueError(
                    "You must specify one of these two options, "
                    "verify_ssl:bool or ssl_context: ssl.SSLContext")

            if "verify_ssl" in options.keys():
                value = options.get("verify_ssl", None)
                if type(value) is not bool:
                    raise TypeError("Verify ssl must be a bool")

                self.ssl_context = create_ssl_context(value)

            if "ssl_context" in options.keys():
                value = options.get("ssl_context", None)
                if type(value) is not ssl.SSLContext:
                    raise TypeError("ssl_context must be a ssl.SSLContext")
                self.ssl_context = value

            if "headers" in options.keys():
                value = options.get("headers", None)
                if type(value) is not dict:
                    raise TypeError("headers must be a Dict[str, str]")
                self.headers.update(value)

            if "access_token_factory" in options.keys():
                auth_function = options.get("access_token_factory", None)
                if auth_function is None\
                        or not callable(auth_function):
                    raise TypeError(
                        "access_token_factory is not function")
                self.auth_function = auth_function

        self.hub_url = hub_url
        self.options = self.options if options is None else options
        return self

    def configure_logging(
            self, logging_level, socket_trace=False, handler=None):
        """Configures signalr logging

        Args:
            logging_level ([type]): logging.INFO | logging.DEBUG ...
                from python logging class
            socket_trace (bool, optional): Enables socket package trace.
                Defaults to False.
            handler ([type], optional):  Custom logging handler.
                Defaults to None.

        Returns:
            [HubConnectionBuilder]: Instance hub with logging configured
        """
        Helpers.configure_logger(logging_level, handler)
        self.enable_trace = socket_trace
        return self

    def configure_proxies(
            self,
            proxies: dict):
        """configures proxies

        Args:
            proxies (dict): {
              "http"  : "http://host:port",
              "https" : "https://host:port",
              "ftp"   : "ftp://port:port"
            }

        Returns:
            [HubConnectionBuilder]: Instance hub with proxies configured
        """

        if "http" not in proxies.keys() or "https" not in proxies.keys():
            raise ValueError("Only http and https keys are allowed")

        self.proxies = proxies
        return self

    def with_hub_protocol(self, protocol):
        """Changes transport protocol
            from signalrcore.types\
                import HubProtocolEncoding

            HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
                ...
            .with_hub_protocol(HubProtocolEncoding.binary)\
                ...
            .build()
        Args:
            protocol(
                    MessagePackHubProtocol|
                    JsonHubProtocol|
                    HubProtocolEncoding):
                protocol instance or HubProtocolEncoding

        Returns:
            HubConnectionBuilder: instance configured
        """
        if issubclass(type(protocol), BaseHubProtocol):
            self.protocol = protocol
            return self

        if type(protocol) is HubProtocolEncoding:
            self.preferred_protocol = protocol
            return self

        raise TypeError(f"Wrong protocol type {type(protocol)}")

    def build(self):
        """Creates the connection hub

        Returns:
            [BaseHubConnection]: [connection SignalR object]
        """
        return AuthHubConnection(
                headers=self.headers,
                auth_function=self.auth_function,
                url=self.hub_url,
                protocol=self.protocol,
                preferred_protocol=self.preferred_protocol,
                keep_alive_interval=self.keep_alive_interval,
                reconnection_handler=self.reconnection_handler,
                ssl_context=self.ssl_context,
                proxies=self.proxies,
                skip_negotiation=self.skip_negotiation,
                enable_trace=self.enable_trace,
                preferred_transport=self.preferred_transport)\
            if self.has_auth_configured else\
            BaseHubConnection(
                url=self.hub_url,
                protocol=self.protocol,
                preferred_protocol=self.preferred_protocol,
                keep_alive_interval=self.keep_alive_interval,
                reconnection_handler=self.reconnection_handler,
                headers=self.headers,
                ssl_context=self.ssl_context,
                proxies=self.proxies,
                skip_negotiation=self.skip_negotiation,
                enable_trace=self.enable_trace,
                preferred_transport=self.preferred_transport)

    def with_automatic_reconnect(self, data: dict):
        """Configures automatic reconnection
            https://devblogs.microsoft.com/aspnet/asp-net-core-updates-in-net-core-3-0-preview-4/

            hub = HubConnectionBuilder()\
            .with_url(self.server_url, options={"verify_ssl":False})\
            .configure_logging(logging.ERROR)\
            .with_automatic_reconnect({
                "type": "raw",
                "keep_alive_interval": 10,
                "reconnect_interval": 5,
                "max_attempts": 5
            })\
            .build()

        Args:
            data (dict): [dict with automatic reconnection parameters]

        Returns:
            [HubConnectionBuilder]: [self object for fluent interface purposes]
        """
        reconnect_type = data.get("type", "raw")

        # Infinite reconnect attempts
        max_attempts = data.get("max_attempts", None)

        # 5 sec interval
        reconnect_interval = data.get("reconnect_interval", 5)

        keep_alive_interval = data.get("keep_alive_interval", 15)

        intervals = data.get("intervals", [])  # Reconnection intervals

        self.keep_alive_interval = keep_alive_interval

        reconnection_type = ReconnectionType[reconnect_type]

        if reconnection_type == ReconnectionType.raw:
            self.reconnection_handler = RawReconnectionHandler(
                reconnect_interval,
                max_attempts
            )
        if reconnection_type == ReconnectionType.interval:
            self.reconnection_handler = IntervalReconnectionHandler(
                intervals
            )
        return self
