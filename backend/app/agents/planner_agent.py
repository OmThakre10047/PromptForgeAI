from app.agents.base_agent import BaseAgent
from app.prompts.planner import get_planner_prompt


class PlannerAgent(BaseAgent):

    SYSTEM_PROMPT = get_planner_prompt()

    def get_task(self):
        return "planning"