from app.graph.workflow import workflow
from app.services.state_factory import StateFactory

class WorkflowService:

    @staticmethod
    async def solve(
        problem: str,
        acceptance_score: int = 95,
    ):

        state = StateFactory.create(
            problem,
        )

        return await workflow.ainvoke(state)