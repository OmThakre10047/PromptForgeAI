from app.agents.base_agent import BaseAgent
from app.engine.state import ProjectState


class DeveloperAgent(BaseAgent):

    async def run(
        self,
        state: ProjectState
    ) -> ProjectState:

        system_prompt = """
You are an expert Competitive Programming developer.

Generate the best possible solution.
Return only the code.
"""

        response = await self.provider.generate(
            system_prompt,
            state.task
        )

        state.current_solution = response

        state.log("Developer Agent generated a solution.")

        return state