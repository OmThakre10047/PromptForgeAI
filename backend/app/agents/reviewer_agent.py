from app.agents.base_agent import BaseAgent
from app.prompts.reviewer import get_reviewer_prompt


class ReviewerAgent(BaseAgent):

    SYSTEM_PROMPT = get_reviewer_prompt()
    
    def get_task(self):
        return "review"