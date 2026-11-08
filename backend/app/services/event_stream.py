import asyncio

class EventStream:

    def __init__(self):
        self.queue = asyncio.Queue()

    async def send(self, event: dict):
        await self.queue.put(event)

    async def receive(self):
        return await self.queue.get()