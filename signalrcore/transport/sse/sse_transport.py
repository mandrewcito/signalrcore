from ..base_transport import BaseTransport


class SSETransport(BaseTransport):
    async def connect(self, url, headers):
        headers["Accept"] = "text/event-stream"
        # self.session = aiohttp.ClientSession()
        self.response = await self.session.get(url, headers=headers)

    async def receive(self):
        async for line in self.response.content:
            if line.startswith(b"data:"):
                yield line[5:].strip()

    async def send(self, data):
        await self.session.post(self.send_url, data=data)

    async def close(self):
        await self.session.close()
