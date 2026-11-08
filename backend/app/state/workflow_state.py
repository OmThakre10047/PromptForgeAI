from typing import Optional
from pydantic import BaseModel  

class WorkflowState(BaseModel):
    problem: str
    plan: Optional[str] = None
    solution: Optional[str] = None
    review: Optional[str] = None
    repaired_solution: Optional[str] = None
    final_solution: Optional[str] = None