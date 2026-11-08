from pydantic import BaseModel

class AgentResponse(BaseModel):
    agent_name: str
    success: bool
    content: str