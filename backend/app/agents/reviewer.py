from app.agents.base_agent import BaseAgent
from app.engine.state import ProjectState
from app.core.prompt_loader import PromptLoader

class TesterAgent(BaseAgent):

    async def run(self, state: ProjectState) -> ProjectState:

        system_prompt = PromptLoader.load("tester")

        response = await self.provider.generate(
            system_prompt,
            state.current_solution
        )

        state.hidden_tests = response.split("\n")
        state.log("Tester Agent generated hidden tests.")
        return state