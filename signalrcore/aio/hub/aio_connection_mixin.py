import asyncio
import copy
from typing import Optional

from ...hub.errors import HubConnectionError
from ...hub.negotiation import NegotiateResponse
from ...protocol.protocol_factory import ProtocolFactory
from ...transport.base_transport import TransportState
from ..transport.factory import AIOTransportFactory
from .aio_negotiation import AsyncNegotiationHandler

# A start that never reaches the connected state must not block the caller
# forever (for example a handshake rejected by the server).
AIO_CONNECTION_TIMEOUT = 30


class AIOConnectionMixin(object):
    """Asyncio connection lifecycle shared by the async hub connections."""

    transport = None

    async def _negotiate(self) -> NegotiateResponse:
        """Negotiates the connection with the server.

        Updates url and headers when the server returns them.
        """
        handler = AsyncNegotiationHandler(
            self.url,
            self.headers,
            self.proxies,
            self.ssl_context,
            self.skip_negotiation)

        url, headers, response = await handler.negotiate()

        self.url = url
        self.headers = copy.deepcopy(headers)

        return response

    async def start(self) -> bool:
        """Starts the connection and waits for the handshake.

        Returns:
            bool: True if the connection starts successfully, False if it
            is already connected.
        """
        if self.transport is not None and self.transport.is_connected():
            self.logger.warning("Already connected unable to start")
            return False

        self.logger.debug("Connection started")

        negotiate_response = await self._negotiate()

        self.protocol = ProtocolFactory.create(
                self.preferred_transport,
                self.preferred_protocol,
                negotiate_response)\
            if self._selected_protocol is None else\
            self._selected_protocol

        self.transport = AIOTransportFactory.create(
            negotiate_response,
            self.preferred_transport,
            url=self.url,
            protocol=self.protocol,
            headers=self.headers,
            token=self.token,
            skip_negotiation=self.skip_negotiation,
            connection_id=negotiate_response.get_id(),
            ssl_context=self.ssl_context,
            proxies=self.proxies,
            on_close=self._callbacks.on_close,
            on_open=self._callbacks.on_open,
            on_reconnect=self._callbacks.on_reconnect,
            on_message=self.on_message,
            **self.kwargs
        )

        await self.transport.start()

        transport = self.transport

        try:
            await transport.wait_until(
                lambda: transport.is_connected()
                or transport.is_disconnected(),
                timeout=AIO_CONNECTION_TIMEOUT)
        except asyncio.TimeoutError:
            await transport.stop()
            raise TimeoutError(
                "Timeout waiting for the hub handshake")

        if not transport.is_connected():
            raise HubConnectionError(
                "Connection closed before the handshake completed")

        return True

    async def stop(self) -> None:
        """Stops the connection."""
        self.logger.debug("Connection stop")

        if self.transport is not None:
            await self.transport.stop()

    async def wait_until_state(
            self,
            state: TransportState,
            timeout: Optional[float] = None) -> None:
        """Waits until the transport reaches the requested state."""
        if self.transport is None:
            # No transport means the connection was never started or was
            # already torn down, which is the disconnected state.
            if state == TransportState.disconnected:
                return

            raise TimeoutError(
                f"Timeout waiting for state {state}")

        await self.transport.wait_until_state(state, timeout=timeout)
