from fastapi import FastAPI

from app.api.schemas import SolveRequest
from app.api.stream import router as stream_router
from app.services.state_factory import StateFactory
from app.services.workflow_service import WorkflowService
from app.services.history_service import HistoryService

app = FastAPI(
    title="PromptForge AI",
    version="1.0.0"
)

app.include_router(stream_router)


@app.get("/")
async def root():
    return {
        "message": "PromptForge API is running"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


@app.post("/generate")
async def generate(request: SolveRequest):

    result = await WorkflowService.solve(
        request.problem,
        request.acceptance_score,
    )

    HistoryService.save(result)

    return {
        "plan": result["plan"],
        "solution": result["solution"],
        "review": result["review"],
        "execution": result["execution"],
        "trace": result["trace"],
        "solution_history": result["solution_history"],
        "review_history": result["review_history"],
        "execution_history": result["execution_history"],
        "status": result["final_status"],
    }