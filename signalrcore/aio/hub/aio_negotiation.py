from typing import Tuple

from ...helpers import Helpers
from ...hub.negotiation import (
    NegotiateResponse,
    build_negotiate_request,
    check_negotiate_status,
    parse_negotiate_response,
    skip_negotiate_response,
)
from ..transport.http import request

# Negotiation is a small request; it must not hang a start() forever.
AIO_NEGOTIATE_TIMEOUT = 30


class AsyncNegotiationHandler(object):
    def __init__(
            self,
            url,
            headers,
            proxies,
            ssl_context,
            skip_negotiation):
        self.logger = Helpers.get_logger()
        self.url = url
        self.headers = headers
        self.proxies = proxies
        self.ssl_context = ssl_context
        self.skip_negotiation = skip_negotiation

    async def negotiate(self) -> Tuple[str, dict, NegotiateResponse]:
        if self.skip_negotiation:
            return skip_negotiate_response(self.url, self.headers)

        negotiate_url, headers = build_negotiate_request(
            self.url, self.headers)

        self.logger.debug("Negotiate url:{0}".format(negotiate_url))

        response = await request(
            negotiate_url,
            method="POST",
            headers=headers,
            proxies=self.proxies,
            ssl_context=self.ssl_context,
            timeout=AIO_NEGOTIATE_TIMEOUT)

        self.logger.debug(
            "Negotiate response status code {0}".format(
                response.status_code))

        check_negotiate_status(response.status_code)

        data = response.json()

        self.logger.debug("Negotiate response {0}".format(data))

        return parse_negotiate_response(self.url, headers, data)
