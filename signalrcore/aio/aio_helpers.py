import asyncio
import copy
import json
import ssl
import urllib.request
import urllib.parse as parse

from typing import Union
from ..types import DEFAULT_ENCODING


class AIOHTTPResponse(object):
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content

    def json(self) -> Union[dict, None]:
        response_body = self.content.decode(DEFAULT_ENCODING)
        return json.loads(response_body)\
            if len(response_body) > 0 else None


def _execute_request(
        url, method, headers, data,
        proxy_handler, ssl_context, timeout):

    req = urllib.request.Request(
        url, method=method, headers=headers, data=data)

    if proxy_handler is not None:
        opener = urllib.request.build_opener(proxy_handler)

    else:
        opener = urllib.request.urlopen

    with opener(req, context=ssl_context, timeout=timeout) as response:
        return AIOHTTPResponse(
            response.getcode(), response.read())


class AIORequestHelpers:
    @staticmethod
    def update_querystring(url: str, params: dict = {}) -> str:
        parsed = parse.urlparse(url)

        qs = parse.parse_qs(parsed.query)
        qs.update(params)

        new_query = parse.urlencode(qs, doseq=True)

        return parse.urlunparse(parsed._replace(query=new_query))

    @staticmethod
    async def get(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            params: dict = {},
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> AIOHTTPResponse:
        return await AIORequestHelpers.request(
            url,
            "GET",
            headers=headers,
            proxies=proxies,
            params=params,
            timeout=timeout,
            ssl_context=ssl_context
        )

    @staticmethod
    async def post(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            params: dict = {},
            data: bytes = None,
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> AIOHTTPResponse:
        return await AIORequestHelpers.request(
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
    async def delete(
            url: str,
            headers: dict = {},
            proxies: dict = {},
            params: dict = {},
            data: bytes = None,
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> AIOHTTPResponse:
        return await AIORequestHelpers.request(
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
    async def request(
            url: str,
            method: str,
            headers: dict = None,
            proxies: dict = {},
            params: dict = {},
            data: bytes = None,
            timeout: float = None,
            ssl_context: ssl.SSLContext = None) -> AIOHTTPResponse:

        request_headers = {}

        if headers is None:
            request_headers = {'Content-Type': 'application/json'}

        request_headers = copy.deepcopy(headers)

        if data is not None:
            request_headers.update({"Content-Length": str(len(data))})

        proxy_handler = None
        if len(proxies.keys()) > 0:
            proxy_handler = urllib.request.ProxyHandler(proxies)

        updated_url = AIORequestHelpers.update_querystring(url, params)

        result = await asyncio.to_thread(
            _execute_request,
            updated_url, method, request_headers, data,
            proxy_handler, ssl_context, timeout)

        return result
