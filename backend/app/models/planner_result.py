from pydantic import BaseModel
from app.models.test_case import TestCase

class PlannerResult(BaseModel):
    category: str
    difficulty: str
    algorithm: str
    time_complexity: str
    space_complexity: str
    edge_cases: list[str]
    strategy: str
    sample_tests: list[TestCase] = []