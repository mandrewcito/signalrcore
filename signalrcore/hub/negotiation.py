import copy
from dataclasses import dataclass
from typing import List, Tuple
from ..helpers import Helpers, RequestHelpers
from .errors import UnAuthorizedHubError, HubError
from ..types import HttpTransportType, HubProtocolEncoding


class NegotiateValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AvailableTransport:
    transport: HttpTransportType
    transfer_formats: List[HubProtocolEncoding]

    @classmethod
    def from_dict(cls, data: dict) -> "AvailableTransport":
        if not isinstance(data, dict):
            raise NegotiateValidationError(
                "availableTransports item must be an object")

        transport = HttpTransportType(data.get("transport"))

        transfer_formats = data.get("transferFormats")

        if not isinstance(transfer_formats, list) or not transfer_formats:
            raise NegotiateValidationError(
                f"transferFormats for {transport} must be a non-empty list"
            )

        transfer_formats = [
            HubProtocolEncoding(fmt)
            for fmt in transfer_formats
        ]

        return cls(
            transport=transport,
            transfer_formats=transfer_formats,
        )


@dataclass(frozen=True)
class NegotiateResponse:
    negotiate_version: int
    connection_id: str
    access_token: str
    url: str
    available_transports: List[AvailableTransport]

    def get_id(self) -> str:
        if self.negotiate_version == 0:
            return self.connection_id

        if self.negotiate_version == 1:
            return self.access_token

        raise ValueError(
            f"Negotiate version invalid {self.negotiate_version}")

    @classmethod
    def from_dict(cls, data: dict) -> "NegotiateResponse":
        if not isinstance(data, dict):
            raise NegotiateValidationError(
                "Negotiate response must be a JSON object")

        version = data.get("negotiateVersion")
        if not isinstance(version, int):
            raise NegotiateValidationError(
                "negotiateVersion must be an integer")

        connection_id = data.get("connectionId")
        if not isinstance(connection_id, str) or not connection_id:
            raise NegotiateValidationError(
                "connectionId must be a non-empty string")

        transports = data.get("availableTransports")
        if not isinstance(transports, list) or not transports:
            raise NegotiateValidationError(
                "availableTransports must be a non-empty list")

        parsed_transports = [
            AvailableTransport.from_dict(t) for t in transports
        ]

        access_token = data.get("accessToken", None)
        url = data.get("url", None)

        return cls(
            negotiate_version=version,
            connection_id=connection_id,
            available_transports=parsed_transports,
            access_token=access_token,
            url=url
        )


class NegotiationHandler(object):
    def __init__(
            self,
            url,
            headers,
            proxies,
            verify_ssl):
        self.logger = Helpers.get_logger()
        self.url = url
        self.headers = headers
        self.proxies = proxies
        self.verify_ssl = verify_ssl

    def negotiate(self) -> Tuple[str, dict, NegotiateResponse]:
        url = self.url
        headers = copy.deepcopy(self.headers)
        headers.update({'Content-Type': 'application/json'})

        negotiate_url = Helpers.get_negotiate_url(self.url)

        self.logger.debug("Negotiate url:{0}".format(negotiate_url))

        response = RequestHelpers.post(
            negotiate_url,
            headers=headers,
            proxies=self.proxies,
            verify=self.verify_ssl)

        status_code, data = response.status_code, response.json()

        negotiate_response = NegotiateResponse.from_dict(data)

        self.logger.debug(
            "Negotiate response status code {0}".format(status_code))
        self.logger.debug(
            "Negotiate response {0}".format(negotiate_response))

        if status_code != 200:
            raise HubError(status_code)\
                if status_code != 401 else UnAuthorizedHubError()

        if "connectionId" in data.keys():
            url = Helpers.encode_connection_id(
                self.url, negotiate_response.connection_id)

        # Azure
        if 'url' in data.keys() and 'accessToken' in data.keys():
            Helpers.get_logger().debug(
                "Azure url, reformat headers, token and url {0}".format(data))
            url = negotiate_response.url\
                if negotiate_response.url.startswith("ws") else\
                Helpers.http_to_websocket(negotiate_response.url)
            headers = {
                "Authorization": "Bearer " + negotiate_response.access_token
                }
        return url, headers, negotiate_response
