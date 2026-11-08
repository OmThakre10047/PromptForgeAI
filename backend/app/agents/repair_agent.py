from app.agents.base_agent import BaseAgent
from app.prompts.repair import get_repair_prompt


class RepairAgent(BaseAgent):

    SYSTEM_PROMPT = get_repair_prompt()
    
    def get_task(self):
        return "coding"