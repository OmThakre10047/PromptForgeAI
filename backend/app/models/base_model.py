from abc import ABC, abstractmethod


class BaseModel(ABC):

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass