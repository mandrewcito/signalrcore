import json
import ssl
import copy
import logging
import urllib
import urllib.parse as parse
import urllib.request

from typing import Callable, List, Dict, TypeVar, Union

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
        response_body = self.content.decode('utf-8')
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
            verify: bool = False,
            params: dict = {}) -> HTTPResponse:
        return RequestHelpers.request(
            url,
            "GET",
            headers=headers,
            proxies=proxies,
            verify=verify,
            params=params
        )

    @staticmethod
    def post(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            verify: bool = False,
            params: dict = {},
            data: bytes = None) -> HTTPResponse:
        return RequestHelpers.request(
            url,
            "POST",
            headers=headers,
            proxies=proxies,
            verify=verify,
            params=params,
            data=data
        )

    @staticmethod
    def delete(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            verify: bool = False,
            params: dict = {},
            data: bytes = None) -> HTTPResponse:
        return RequestHelpers.request(
            url,
            "DELETE",
            headers=headers,
            proxies=proxies,
            verify=verify,
            params=params,
            data=data
        )

    @staticmethod
    def request(
            url: str,
            method: str,
            headers: dict = None,
            proxies: dict = {},
            verify: bool = False,
            params: dict = {},
            data: bytes = None) -> HTTPResponse:

        context = ssl.create_default_context()
        request_headers = {}

        if headers is None:
            # pragma: no cover
            request_headers = {'Content-Type': 'application/json'}

        request_headers = copy.deepcopy(headers)

        if data is not None:
            request_headers.update({"Content-Length": str(len(data))})

        if not verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        proxy_handler = None

        if len(proxies.keys()) > 0:
            proxy_handler = urllib.request.ProxyHandler(proxies)
            # pragma: no cover

        updated_url = RequestHelpers.update_querystring(url, params)

        req = urllib.request.Request(
                updated_url,
                method=method,
                headers=request_headers,
                data=data)

        opener = urllib.request.build_opener(proxy_handler)\
            if proxy_handler is not None else\
            urllib.request.urlopen

        with opener(
                req,
                context=context) as response:

            return HTTPResponse(
                context=context,
                request=req,
                response=response
                )


class Helpers:

    @staticmethod
    def configure_logger(level=logging.INFO, handler=None):
        logger = Helpers.get_logger()
        if handler is None:
            handler = logging.StreamHandler()
            debug_formatter = ""\
                if level != logging.DEBUG else\
                "- %(filename)s:%(lineno)d "
            handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s '
                    + debug_formatter +
                    '- %(levelname)s - %(message)s'))
            handler.setLevel(level)
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
    def get_negotiate_url(url):
        querystring = ""
        if Helpers.has_querystring(url):
            url, querystring = Helpers.split_querystring(url)

        url_parts = parse.urlsplit(Helpers.websocket_to_http(url))

        negotiate_suffix = "negotiate"\
            if url_parts.path.endswith('/')\
            else "/negotiate"

        url_parts = url_parts._replace(path=url_parts.path + negotiate_suffix)

        return parse.urlunsplit(url_parts) \
            if querystring == "" else\
            parse.urlunsplit(url_parts) + "?" + querystring

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
