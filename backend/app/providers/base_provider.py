from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """
    Abstract base class for all AI providers.
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """
        Generate a response from the model.
        """
        pass