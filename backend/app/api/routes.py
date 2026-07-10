from fastapi import APIRouter
from pydantic import BaseModel
from app.agents.planner import plan_task

router = APIRouter()

class UserRequest(BaseModel):
    message: str


@router.post("/plan")
def planner(request: UserRequest):
    result = plan_task(request.message)
    return {"result": result}