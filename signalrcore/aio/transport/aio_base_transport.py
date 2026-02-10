import asyncio
import time
from typing import Awaitable

from ...transport.base_transport import BaseTransport, TransportState


class AioBaseTransport(BaseTransport):
    def __init__(self, **kwargs):
        super(AioBaseTransport).__init__(**kwargs)

    async def wait_until_state(
            self,
            state: TransportState,
            timeout: float = None) -> Awaitable:
        t0 = time.time()
        while self.state != state:
            asyncio.sleep(0.1)
            if timeout is not None and t0 + timeout < time.time():
                raise TimeoutError()
