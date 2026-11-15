import json
import ssl
import copy
import logging
import urllib
import urllib.parse as parse
import urllib.request

from typing import Callable, List, Dict, TypeVar, Union
from .types import DEFAULT_ENCODING

T = TypeVar("T")
K = TypeVar("K")


class HTTPResponse(object):
    def __init__(
            self,
            context,
            request,
            response):
        self._context = context
        self._request = request
        self._response = response

        self.status_code = response.getcode()
        self.content = response.read()

    def json(self) -> Union[dict, None]:
        response_body = self.content.decode(DEFAULT_ENCODING)
        return json.loads(response_body)\
            if len(response_body) > 0 else None


class RequestHelpers:
    @staticmethod
    def update_querystring(url: str, params: dict = {}) -> str:
        parsed = parse.urlparse(url)

        qs = parse.parse_qs(parsed.query)
        qs.update(params)

        new_query = parse.urlencode(qs, doseq=True)

        return parse.urlunparse(parsed._replace(query=new_query))

    @staticmethod
    def get(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            params: dict = {},
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> HTTPResponse:
        return RequestHelpers.request(
            url,
            "GET",
            headers=headers,
            proxies=proxies,
            params=params,
            timeout=timeout,
            ssl_context=ssl_context
        )

    @staticmethod
    def post(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            params: dict = {},
            data: bytes = None,
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> HTTPResponse:
        return RequestHelpers.request(
            url,
            "POST",
            headers=headers,
            proxies=proxies,
            params=params,
            data=data,
            timeout=timeout,
            ssl_context=ssl_context
        )

    @staticmethod
    def delete(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            params: dict = {},
            data: bytes = None,
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> HTTPResponse:
        return RequestHelpers.request(
            url,
            "DELETE",
            headers=headers,
            proxies=proxies,
            params=params,
            data=data,
            timeout=timeout,
            ssl_context=ssl_context
        )

    @staticmethod
    def request(
            url: str,
            method: str,
            headers: dict = None,
            proxies: dict = {},
            params: dict = {},
            data: bytes = None,
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> HTTPResponse:

        if headers is None:
            request_headers = {"Content-Type": "application/json"}
        else:
            request_headers = copy.deepcopy(headers)

        if data is not None:
            request_headers["Content-Length"] = str(len(data))

        updated_url = RequestHelpers.update_querystring(url, params)

        req = urllib.request.Request(
                updated_url,
                method=method,
                headers=request_headers,
                data=data)

        handlers = []

        if proxies:
            handlers.append(urllib.request.ProxyHandler(proxies))

        if ssl_context is not None:
            handlers.append(
                urllib.request.HTTPSHandler(context=ssl_context))

        if handlers:
            opener = urllib.request.build_opener(*handlers)
            response = opener.open(req, timeout=timeout)
        else:  # pragma: no cover
            response = urllib.request.urlopen(req, timeout=timeout)

        with response:
            return HTTPResponse(
                context=ssl_context,
                request=req,
                response=response
                )


class Helpers:

    DEFAULT_HANDLER_FLAG = "_signalrcore_default_handler"

    @staticmethod
    def _log_formatter(level):
        debug_formatter = ""\
            if level != logging.DEBUG else\
            "- %(filename)s:%(lineno)d "
        return logging.Formatter(
            '%(asctime)s - %(name)s '
            + debug_formatter +
            '- %(levelname)s - %(message)s')

    @staticmethod
    def configure_logger(level=logging.INFO, handler=None):
        logger = Helpers.get_logger()

        if handler is None:
            # Reuse the handler created by a previous call, otherwise
            # every configure_logging() adds another one and messages
            # are logged once per handler.
            handler = next(
                (existing for existing in logger.handlers
                 if getattr(
                     existing, Helpers.DEFAULT_HANDLER_FLAG, False)),
                None)

            if handler is None:
                handler = logging.StreamHandler()
                setattr(handler, Helpers.DEFAULT_HANDLER_FLAG, True)
                logger.addHandler(handler)

            handler.setFormatter(Helpers._log_formatter(level))
            handler.setLevel(level)
        elif handler not in logger.handlers:
            logger.addHandler(handler)

        logger.setLevel(level)

    @staticmethod
    def get_logger():
        return logging.getLogger("SignalRCoreClient")

    @staticmethod
    def has_querystring(url):
        return "?" in url

    @staticmethod
    def split_querystring(url):
        parts = url.split("?")
        return parts[0], parts[1]

    @staticmethod
    def replace_scheme(
            url,
            root_scheme,
            source,
            secure_source,
            destination,
            secure_destination):
        url_parts = parse.urlsplit(url)

        if root_scheme not in url_parts.scheme:
            if url_parts.scheme == secure_source:
                url_parts = url_parts._replace(scheme=secure_destination)
            if url_parts.scheme == source:
                url_parts = url_parts._replace(scheme=destination)

        return parse.urlunsplit(url_parts)

    @staticmethod
    def websocket_to_http(url):
        return Helpers.replace_scheme(
            url,
            "http",
            "ws",
            "wss",
            "http",
            "https")

    @staticmethod
    def http_to_websocket(url):
        return Helpers.replace_scheme(
            url,
            "ws",
            "http",
            "https",
            "ws",
            "wss"
        )

    @staticmethod
    def get_negotiate_url(url, negotiate_version=None):
        url_parts = parse.urlsplit(Helpers.websocket_to_http(url))

        negotiate_suffix = "negotiate"\
            if url_parts.path.endswith('/')\
            else "/negotiate"

        url_parts = url_parts._replace(
            path=url_parts.path + negotiate_suffix)

        query = parse.parse_qs(url_parts.query)

        if negotiate_version is not None:
            query["negotiateVersion"] = [str(negotiate_version)]

        url_parts = url_parts._replace(
            query=parse.urlencode(query, doseq=True))

        return parse.urlunsplit(url_parts)

    @staticmethod
    def encode_connection_id(url, id):
        url_parts = parse.urlsplit(url)
        query_string_parts = parse.parse_qs(url_parts.query)
        query_string_parts["id"] = id

        url_parts = url_parts._replace(
            query=parse.urlencode(
                query_string_parts,
                doseq=True))

        return Helpers.http_to_websocket(parse.urlunsplit(url_parts))

    @staticmethod
    def get_port(parsed_url) -> int:
        port = parsed_url.port
        is_secure_connection = parsed_url.scheme in ("wss", "https")

        if not port:  # pragma: no cover
            port = 80
            if is_secure_connection:  # pragma: no cover
                port = 443
        return port

    @staticmethod
    def get_proxy_info(
            is_secure_connection: bool,
            proxies: dict):
        proxy_info = None

        if is_secure_connection\
                and proxies.get("https", None) is not None:
            proxy_info = parse.urlparse(proxies.get("https"))

        if not is_secure_connection\
                and proxies.get("http", None) is not None:
            proxy_info = parse.urlparse(proxies.get("http"))

        return proxy_info


class ListHelpers:
    @staticmethod
    def list_to_dict(
            elements: List[T],
            key: Callable[[T], K]) -> Dict[T, K]:
        return {
            key(e): e
            for e in elements
        }
