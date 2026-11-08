from pydantic import BaseModel

class ReviewResult(BaseModel):
    overall_score: int
    correctness: int
    efficiency: int
    edge_cases: int
    code_quality: int
    explanation: int

    issues: list[str]

    recommendation: str

    passed_tests: int = 0
    total_tests: int = 0