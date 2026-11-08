import time
from abc import ABC
from typing import Any


from app.models.agent_result import AgentResult
from app.services.llm_service import LLMService


class BaseAgent(ABC):
    """
    Base class for every AI Agent in PromptForge.
    """

    SYSTEM_PROMPT = ""
    TASK = "general"

    def __init__(self):

        self.llm = LLMService()

        self.agent_name = self.__class__.__name__

    async def generate(
        self,
        user_prompt: str,
    ) -> AgentResult:

        start = time.perf_counter()

        provider_result = await self.llm.generate(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            task=self.get_task(),
        )

        latency = time.perf_counter() - start

        return AgentResult(
            agent=self.agent_name,
            model=provider_result["model"],
            latency=round(latency,2),
            response=provider_result["response"],
        )
    
    def get_task(self):

        return "general"