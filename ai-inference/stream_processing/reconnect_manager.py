import asyncio


class ReconnectManager:
    def __init__(self) -> None:
        self.attempts = 0

    async def wait(self) -> None:
        self.attempts += 1
        await asyncio.sleep(min(2**self.attempts, 30))

    def reset(self) -> None:
        self.attempts = 0
