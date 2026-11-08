from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from app.schemas.models import ExecutionReport, FailureAnalysis, Plan, Review, TestCase


class PipelineState(TypedDict, total=False):
    # ---- request ----
    run_id: str
    problem: str
    language: str
    acceptance_score: int
    max_repairs: int
    max_replans: int
    max_refinements: int

    # ---- planning / generation ----
    plan: Plan
    plan_model: str
    solution: str
    solution_origin: str          # solver | repair | refine | replan
    solution_model: str

    # ---- testing ----
    raw_tests: list[TestCase]
    tester_model: str
    oracle_code: str
    oracle_model: str
    tests: list[TestCase]
    oracle_report: dict
    pruned_tests: Annotated[list[dict], operator.add]

    # ---- execution / analysis / review ----
    execution: ExecutionReport
    analysis: FailureAnalysis | None
    analysis_model: str
    review: Review | None
    score: int
    best: dict                    # {code, report, version, score}
    version: int
    versions: Annotated[list[dict], operator.add]

    # ---- loop control ----
    repair_attempts: int
    replans: int
    refinements: int
    stagnation: int
    retest: bool
    repair_history: Annotated[list[str], operator.add]

    # ---- outcome / observability ----
    status: str
    fatal: str
    final: dict
    trace: Annotated[list[dict], operator.add]
    events: Annotated[list[dict], operator.add]
    errors: Annotated[list[str], operator.add]


def initial_state(
    run_id: str,
    problem: str,
    language: str,
    acceptance_score: int,
    max_repairs: int,
    max_replans: int,
    max_refinements: int,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "problem": problem,
        "language": language,
        "acceptance_score": acceptance_score,
        "max_repairs": max_repairs,
        "max_replans": max_replans,
        "max_refinements": max_refinements,
        "solution": "",
        "solution_origin": "",
        "raw_tests": [],
        "oracle_code": "",
        "tests": [],
        "analysis": None,
        "review": None,
        "score": 0,
        "best": {},
        "version": 0,
        "repair_attempts": 0,
        "replans": 0,
        "refinements": 0,
        "stagnation": 0,
        "retest": False,
        "status": "running",
        "fatal": "",
    }
