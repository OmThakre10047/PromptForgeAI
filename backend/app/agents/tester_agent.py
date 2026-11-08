from app.agents.base_agent import BaseAgent
from app.prompts.tester import get_tester_prompt


class TesterAgent(BaseAgent):

    SYSTEM_PROMPT = get_tester_prompt()

    def get_task(self):
        return "testing"