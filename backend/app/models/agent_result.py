from pydantic import BaseModel

class AgentResult(BaseModel):
    agent: str
    model: str
    latency: float
    response: str
    