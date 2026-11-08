from app.agents.base_agent import BaseAgent
from app.prompts.edge_case_expert_prompt import SYSTEM_PROMPT


class EdgeCaseExpert(BaseAgent):

    SYSTEM_PROMPT = SYSTEM_PROMPT