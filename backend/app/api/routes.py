from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.execution.sandbox import execute
from app.llm.router import TASK_PROFILES
from app.schemas.models import TestCase

router = APIRouter(prefix="/api")


class SolveRequest(BaseModel):
    problem: str = Field(min_length=10, max_length=20_000)
    language: Literal["cpp", "python"] | None = None
    acceptance_score: int | None = Field(default=None, ge=0, le=100)
    max_repairs: int | None = Field(default=None, ge=0, le=10)
    max_replans: int | None = Field(default=None, ge=0, le=3)
    max_refinements: int | None = Field(default=None, ge=0, le=3)


class ExecuteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100_000)
    language: Literal["cpp", "python"] = "cpp"
    tests: list[TestCase] = Field(min_length=1, max_length=50)


def _service(request: Request):
    return request.app.state.runs


@router.get("/health")
async def health(request: Request):
    svc = _service(request)
    return {
        "status": "ok",
        "mock_mode": svc.settings.mock_enabled,
        "models": len(svc.llm.catalog.models),
        "providers": sorted(svc.llm.providers),
        "routing_strategy": svc.llm.router.strategy,
    }


@router.post("/solve")
async def solve(body: SolveRequest, request: Request):
    """Run the whole multi-agent pipeline and return the final result."""
    return await _service(request).run(**body.model_dump())


@router.post("/solve/stream")
async def solve_stream(body: SolveRequest, request: Request):
    """Server-Sent Events: one `node` event per completed graph step, then a `result` event."""
    svc = _service(request)

    async def gen():
        try:
            async for item in svc.stream(**body.model_dump()):
                yield f"data: {json.dumps(item, default=str)}\n\n"
        except Exception as exc:  # surface failures to the client instead of a broken stream
            yield f"data: {json.dumps({'type': 'error', 'error': f'{type(exc).__name__}: {exc}'})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/execute")
async def run_code(body: ExecuteRequest, request: Request):
    """Run arbitrary code against tests in the sandbox (no LLM involved)."""
    report = await execute(body.code, body.tests, body.language, _service(request).settings)
    return report.to_api()


@router.get("/models")
async def models(request: Request, task: str = Query("coding")):
    """Model catalog with the router's live ranking for a task."""
    if task not in TASK_PROFILES:
        raise HTTPException(400, f"unknown task; choose from {sorted(TASK_PROFILES)}")
    llm = _service(request).llm
    catalog = {m.id: m.to_dict() for m in llm.catalog.models}
    ranking = llm.router.leaderboard(llm.catalog.models, task)
    for row in ranking:
        row["model"] = catalog.get(row["model_id"], {})
    return {"task": task, "tasks": sorted(TASK_PROFILES), "strategy": llm.router.strategy, "ranking": ranking}


@router.get("/routing/preview")
async def routing_preview(request: Request):
    """Which model the router would pick right now for every task."""
    llm = _service(request).llm
    return {task: llm.route(task).to_dict(limit=3) for task in TASK_PROFILES}


@router.get("/telemetry")
async def telemetry(request: Request):
    return _service(request).llm.telemetry.snapshot()


@router.delete("/telemetry")
async def reset_telemetry(request: Request):
    _service(request).llm.telemetry.reset()
    return {"reset": True}


@router.post("/models/refresh")
async def refresh_models(request: Request):
    models = _service(request).llm.catalog.refresh()
    return {"models": len(models)}


@router.get("/runs")
async def runs(request: Request, limit: int = Query(50, ge=1, le=200)):
    return _service(request).history.list(limit)


@router.get("/runs/{run_id}")
async def run_detail(run_id: str, request: Request):
    record = _service(request).history.get(run_id)
    if not record:
        raise HTTPException(404, "run not found")
    return record
