from pydantic import BaseModel


class PlannerOutput(BaseModel):

    category: str

    difficulty: str

    algorithm: str

    time_complexity: str

    space_complexity: str

    edge_cases: list[str]

    strategy: str