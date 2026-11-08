from app.agents.base_agent import BaseAgent
from app.prompts.solver import get_solver_prompt

class SolverAgent(BaseAgent):
    
    SYSTEM_PROMPT = get_solver_prompt()
    
    def get_task(self):
        return "coding"