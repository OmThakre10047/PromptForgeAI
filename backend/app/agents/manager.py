from app.agents.base_agent import BaseAgent
from app.engine.state import ProjectState
from app.core.prompt_loader import PromptLoader


class ManagerAgent(BaseAgent):

    async def run(self, state: ProjectState) -> ProjectState:

        system_prompt = PromptLoader.load("manager")

        response = await self.provider.generate(
            system_prompt,
            state.task
        )

        state.log("Manager Agent created execution plan.")

        return state