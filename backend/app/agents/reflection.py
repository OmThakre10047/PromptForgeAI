from app.agents.base_agent import BaseAgent
from app.engine.state import ProjectState
from app.core.prompt_loader import PromptLoader


class ReflectionAgent(BaseAgent):

    async def run(self, state: ProjectState) -> ProjectState:

        system_prompt = PromptLoader.load("reflection")

        response = await self.provider.generate(
            system_prompt,
            state.review
        )

        state.reflection = response

        state.log("Reflection Agent analyzed the failure.")

        return state