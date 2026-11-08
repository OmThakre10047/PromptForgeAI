from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ProviderError(Exception):
    """Raised when a provider call fails; `kind` feeds router telemetry."""

    def __init__(self, message: str, kind: str = "error"):
        super().__init__(message)
        self.kind = kind  # "error" | "rate_limit" | "empty" | "timeout"


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> ProviderResponse: ...
