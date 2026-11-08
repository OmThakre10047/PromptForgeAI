"""Run orchestration service: executes the workflow, streams updates, persists history."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, is_dataclass
from typing import Any, AsyncIterator

from pydantic import BaseModel

from app.core.config import Settings, settings as default_settings
from app.llm.service import LLMService
from app.pipeline.graph import build_workflow
from app.pipeline.state import initial_state
from app.schemas.models import ExecutionReport

RECURSION_LIMIT = 150


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, ExecutionReport):
        return obj.to_api()
    if isinstance(obj, BaseModel):
        return to_jsonable(obj.model_dump())
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def summarize_result(state: dict, started: float) -> dict:
    """Compact, JSON-safe view of a finished run (API response + history record)."""
    trace = state.get("trace", [])
    models_used: dict[str, int] = {}
    for call in trace:
        models_used[call["model"]] = models_used.get(call["model"], 0) + 1
    return to_jsonable({
        "run_id": state.get("run_id"),
        "problem": state.get("problem"),
        "language": state.get("language"),
        "status": state.get("status"),
        "final": state.get("final", {}),
        "plan": state.get("plan"),
        "tests": state.get("tests", []),
        "pruned_tests": state.get("pruned_tests", []),
        "oracle_report": state.get("oracle_report", {}),
        "execution": state.get("best", {}).get("report") or state.get("execution"),
        "analysis": state.get("analysis"),
        "review": state.get("review"),
        "versions": state.get("versions", []),
        "trace": trace,
        "events": state.get("events", []),
        "errors": state.get("errors", []),
        "metrics": {
            "duration_s": round(time.time() - started, 3),
            "llm_calls": len(trace),
            "llm_latency_s": round(sum(c.get("latency", 0) for c in trace), 3),
            "fallbacks": sum(max(0, len(c.get("attempts", [])) - 1) for c in trace),
            "models_used": models_used,
            "versions": len(state.get("versions", [])),
        },
        "created_at": started,
    })


class HistoryStore:

    def __init__(self, settings: Settings):
        self.path = settings.history_file
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def save(self, record: dict, keep: int = 200) -> None:
        with self._lock:
            items = [r for r in self._read() if r.get("run_id") != record.get("run_id")]
            items.append(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(items[-keep:], indent=1), encoding="utf-8")

    def list(self, limit: int = 50) -> list[dict]:
        items = self._read()[-limit:][::-1]
        return [{
            "run_id": r.get("run_id"), "status": r.get("status"), "language": r.get("language"),
            "problem": (r.get("problem") or "")[:160], "created_at": r.get("created_at"),
            "passed": r.get("final", {}).get("passed"), "total": r.get("final", {}).get("total"),
            "score": r.get("final", {}).get("score"), "duration_s": r.get("metrics", {}).get("duration_s"),
        } for r in items]

    def get(self, run_id: str) -> dict | None:
        return next((r for r in self._read() if r.get("run_id") == run_id), None)


class RunService:

    def __init__(self, llm: LLMService | None = None, settings: Settings = default_settings):
        self.settings = settings
        self.llm = llm or LLMService(settings)
        self.history = HistoryStore(settings)

    def _init(self, problem: str, language: str | None, acceptance_score: int | None,
              max_repairs: int | None, max_replans: int | None, max_refinements: int | None):
        language = (language or self.settings.DEFAULT_LANGUAGE).lower()
        if language not in ("cpp", "python"):
            raise ValueError("language must be 'cpp' or 'python'")
        state = initial_state(
            run_id=uuid.uuid4().hex[:12],
            problem=problem.strip(),
            language=language,
            acceptance_score=self.settings.ACCEPTANCE_SCORE if acceptance_score is None else acceptance_score,
            max_repairs=self.settings.MAX_REPAIRS if max_repairs is None else max_repairs,
            max_replans=self.settings.MAX_REPLANS if max_replans is None else max_replans,
            max_refinements=self.settings.MAX_REFINEMENTS if max_refinements is None else max_refinements,
        )
        return build_workflow(self.llm, language, self.settings), state

    async def run(self, problem: str, language: str | None = None, acceptance_score: int | None = None,
                  max_repairs: int | None = None, max_replans: int | None = None,
                  max_refinements: int | None = None, save: bool = True) -> dict:
        started = time.time()
        workflow, state = self._init(problem, language, acceptance_score, max_repairs, max_replans, max_refinements)
        final_state = await workflow.ainvoke(state, {"recursion_limit": RECURSION_LIMIT})
        result = summarize_result(final_state, started)
        if save:
            self.history.save(result)
        return result

    async def stream(self, problem: str, language: str | None = None, acceptance_score: int | None = None,
                     max_repairs: int | None = None, max_replans: int | None = None,
                     max_refinements: int | None = None, save: bool = True) -> AsyncIterator[dict]:
        """Yield {"type": "start"|"node"|"result"|"error", ...} events as the graph runs."""
        started = time.time()
        workflow, state = self._init(problem, language, acceptance_score, max_repairs, max_replans, max_refinements)
        yield {"type": "start", "run_id": state["run_id"], "language": state["language"], "mock": self.settings.mock_enabled}
        final_state: dict = state
        async for mode, chunk in workflow.astream(
            state, {"recursion_limit": RECURSION_LIMIT}, stream_mode=["updates", "values"],
        ):
            if mode == "values":
                final_state = chunk
                continue
            for node_name, update in chunk.items():
                update = update or {}
                yield {
                    "type": "node",
                    "node": node_name,
                    "events": to_jsonable(update.get("events", [])),
                    "trace": to_jsonable(update.get("trace", [])),
                    "update": to_jsonable({k: v for k, v in update.items()
                                           if k not in ("events", "trace", "best")}),
                }
        result = summarize_result(final_state, started)
        if save:
            self.history.save(result)
        yield {"type": "result", "result": result}
