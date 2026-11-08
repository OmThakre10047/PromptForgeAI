from abc import ABC, abstractmethod


class BaseProvider(ABC):

    @abstractmethod
    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ):
        pass