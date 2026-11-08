from pydantic import BaseModel


class SolveRequest(BaseModel):
    problem: str
    acceptance_score: int = 95


class SolveResponse(BaseModel):
    status: str
    solution: str
    review: dict
    trace: list