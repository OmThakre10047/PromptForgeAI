"""LangGraph node implementations.

Each node returns a *partial* state update (required for the parallel
solver/tester/oracle fan-out) plus `trace` (agent calls) and `events`
(human-readable timeline) entries that are streamed to the UI.

Outcome feedback to the router (`record_reward`) happens here, because only
the pipeline knows whether a model's work actually helped:
  * solver / repair  -> pass-rate of the code they produced
  * analyzer         -> 1 if the repair that followed its diagnosis improved results
  * tester           -> fraction of its expected outputs confirmed by a trusted oracle
  * oracle           -> 1 if it passed calibration on the ground-truth samples
  * planner          -> best pass-rate achieved from its plan
"""

from __future__ import annotations

import time
from functools import wraps

from app.agents.agents import (
    AnalyzerAgent, OracleAgent, PlannerAgent, RepairAgent, ReviewerAgent, SolverAgent,
    TesterAgent, fmt_failures,
)
from app.core.config import Settings
from app.core.logger import get_logger
from app.execution.sandbox import execute
from app.execution.validation import summarize, validate_tests
from app.llm.service import LLMService
from app.schemas.models import ExecutionReport, FailureAnalysis, Review

log = get_logger("pipeline")

SCORE_WEIGHTS = {"correctness": 0.45, "efficiency": 0.20, "edge_cases": 0.15, "code_quality": 0.10, "readability": 0.10}


def event(node: str, message: str, **data) -> dict:
    return {"node": node, "message": message, "ts": time.time(), **({"data": data} if data else {})}


def node(name: str, fatal: bool = False):
    """Time a node, convert agent exceptions into events, optionally mark the run fatal."""

    def deco(fn):
        @wraps(fn)
        async def wrapper(self, state):
            start = time.perf_counter()
            try:
                update = await fn(self, state) or {}
            except Exception as exc:  # agent/LLM/sandbox failure
                log.exception("node %s failed", name)
                update = {
                    "errors": [f"{name}: {type(exc).__name__}: {exc}"[:500]],
                    "events": [event(name, f"failed: {type(exc).__name__}: {str(exc)[:200]}", level="error")],
                }
                if fatal:
                    update["fatal"] = f"{name} failed: {exc}"[:500]
                else:
                    update.update(await self.fallback(name, state, exc))
            update.setdefault("events", [])
            update["events"] = list(update["events"]) + [
                event(name, "done", duration_ms=round((time.perf_counter() - start) * 1000, 1))
            ]
            return update
        return wrapper
    return deco


def composite_score(review: Review, pass_rate: float) -> int:
    parts = {
        "correctness": min(review.correctness, round(100 * pass_rate)) if review.correctness else round(100 * pass_rate),
        "efficiency": review.efficiency,
        "edge_cases": review.edge_cases,
        "code_quality": review.code_quality,
        "readability": review.readability,
    }
    return int(round(sum(SCORE_WEIGHTS[k] * v for k, v in parts.items())))


class PipelineNodes:

    def __init__(self, llm: LLMService, language: str, settings: Settings):
        self.llm = llm
        self.settings = settings
        self.language = language
        self.planner = PlannerAgent(llm, language)
        self.solver = SolverAgent(llm, language)
        self.tester = TesterAgent(llm, language)
        self.oracle = OracleAgent(llm, language)
        self.analyzer = AnalyzerAgent(llm, language)
        self.repairer = RepairAgent(llm, language)
        self.reviewer = ReviewerAgent(llm, language)

    def reward(self, model: str | None, task: str, value: float) -> None:
        if model:
            self.llm.telemetry.record_reward(model, task, value)

    # -------------------------------------------------------------- fallbacks
    async def fallback(self, name: str, state, exc: Exception) -> dict:
        if name == "generate_tests":
            return {"raw_tests": []}
        if name == "write_oracle":
            return {"oracle_code": ""}
        if name == "analyze":
            report: ExecutionReport = state["best"]["report"]
            category = "compile_error" if not report.compiled else (
                "timeout" if report.verdict_counts.get("TLE") else
                "runtime_error" if report.verdict_counts.get("RE") else "wrong_answer")
            return {"analysis": FailureAnalysis(
                category=category, root_cause="Automatic analysis unavailable; see failing tests.",
                fix_strategy="Fix the failures shown in the test report.", confidence=0.1), "retest": False}
        if name == "review":
            review = Review(correctness=100, efficiency=70, edge_cases=70, code_quality=70, readability=70,
                            issues=["Automated review unavailable"])
            return {"review": review, "score": composite_score(review, 1.0)}
        if name in ("repair", "refine"):
            key = "repair_attempts" if name == "repair" else "refinements"
            return {key: state.get(key, 0) + 1, "stagnation": state.get("stagnation", 0) + 1}
        return {}

    # ------------------------------------------------------------------ nodes
    @node("plan", fatal=True)
    async def plan(self, state):
        plan, calls = await self.planner.plan(state["problem"])
        return {
            "plan": plan,
            "plan_model": calls[-1].model,
            "trace": [c.to_dict() for c in calls],
            "events": [event("plan", f"{plan.algorithm} ({plan.time_complexity}); "
                                     f"{len(plan.sample_tests)} sample test(s) extracted", model=calls[-1].model)],
        }

    @node("solve", fatal=True)
    async def solve(self, state):
        code, calls = await self.solver.solve(state["problem"], state["plan"])
        return {
            "solution": code, "solution_origin": "solver", "solution_model": calls[-1].model,
            "trace": [c.to_dict() for c in calls],
            "events": [event("solve", f"generated {len(code.splitlines())} lines", model=calls[-1].model)],
        }

    @node("generate_tests")
    async def generate_tests(self, state):
        tests, calls = await self.tester.generate_tests(state["problem"], state.get("plan"))
        return {
            "raw_tests": tests, "tester_model": calls[-1].model,
            "trace": [c.to_dict() for c in calls],
            "events": [event("generate_tests", f"{len(tests)} hidden tests generated", model=calls[-1].model)],
        }

    @node("write_oracle")
    async def write_oracle(self, state):
        code, calls = await self.oracle.reference(state["problem"])
        return {
            "oracle_code": code, "oracle_model": calls[-1].model,
            "trace": [c.to_dict() for c in calls],
            "events": [event("write_oracle", "brute-force reference written", model=calls[-1].model)],
        }

    @node("validate_tests")
    async def validate_tests(self, state):
        samples = state["plan"].sample_tests
        tests, report = await validate_tests(
            samples, state.get("raw_tests", []), state.get("oracle_code") or None, self.language, self.settings,
        )
        if report.trusted and (report.verified + report.corrected):
            self.reward(state.get("tester_model"), "testing", report.verified / (report.verified + report.corrected))
        if report.samples_total and report.compiled:
            self.reward(state.get("oracle_model"), "oracle", 1.0 if report.trusted else 0.0)
        summary = summarize(tests)
        labels = {"ground_truth": "from the statement", "verified": "oracle-verified",
                  "corrected": "corrected by oracle", "unverified": "unverified"}
        parts = ", ".join(f"{n} {labels[k]}" for k, n in summary.by_validation.items())
        msg = (f"{summary.total} tests ({parts}); oracle "
               f"{'trusted' if report.trusted else 'not trusted'}: {report.reason}")
        return {
            "tests": tests,
            "oracle_report": report.model_dump(),
            "events": [event("validate_tests", msg, corrected=report.corrected, verified=report.verified)],
        }

    @node("execute")
    async def execute(self, state):
        best = state.get("best") or {}
        retest = bool(state.get("retest"))
        # A re-test (after invalid tests were pruned) re-runs the best version on the new suite.
        code = best["code"] if retest and best.get("code") else state["solution"]
        report = await execute(code, state["tests"], self.language, self.settings)
        version = state.get("version", 0) + 1
        origin = "retest" if retest else state.get("solution_origin", "solver")
        prev: ExecutionReport | None = best.get("report")
        prev_passed = prev.passed if prev else -1

        # Downstream reward for the model that wrote this version.
        task = {"solver": "coding", "replan": "coding", "repair": "repair", "refine": "repair"}.get(origin, "coding")
        if not retest:
            self.reward(state.get("solution_model"), task, report.pass_rate if report.compiled else 0.0)
        if origin == "repair":
            self.reward(state.get("analysis_model"), "analysis", 1.0 if report.passed > prev_passed else 0.0)

        update: dict = {"execution": report, "version": version, "retest": False}
        improved = retest or prev is None or (report.passed, report.compiled) > (prev.passed, prev.compiled)
        if improved or (report.all_passed and origin == "refine"):
            update["best"] = {"code": code, "report": report, "version": version, "score": state.get("score", 0)}
        if origin == "repair":
            update["stagnation"] = 0 if (prev is None or report.passed > prev.passed) else state.get("stagnation", 0) + 1
            if report.passed <= prev_passed:
                update["repair_history"] = [
                    f"Attempt {state.get('repair_attempts', 0)} ({state.get('solution_model')}): "
                    f"{report.passed}/{report.total} passed (no improvement over best {prev_passed}). "
                    f"Verdicts {report.verdict_counts}."
                ]

        status = "compile error" if not report.compiled else f"{report.passed}/{report.total} passed"
        update["versions"] = [{
            "version": version, "origin": origin, "model": state.get("solution_model"),
            "passed": report.passed, "total": report.total, "compiled": report.compiled,
            "verdicts": report.verdict_counts, "code": code,
            "results": [r.verdict for r in report.results],
        }]
        update["events"] = [event("execute", f"v{version} ({origin}): {status}", **report.summary())]
        return update

    @node("analyze")
    async def analyze(self, state):
        best = state["best"]
        report: ExecutionReport = best["report"]
        analysis, calls = await self.analyzer.analyze(
            state["problem"], state["plan"], best["code"], report, "\n".join(state.get("repair_history", [])[-3:]),
        )
        update = {
            "analysis": analysis, "analysis_model": calls[-1].model,
            "trace": [c.to_dict() for c in calls],
            "events": [event("analyze", f"{analysis.category}: {analysis.root_cause[:160]}",
                             needs_replan=analysis.needs_replan, confidence=analysis.confidence)],
        }
        # Analyzer may attribute a failure to a broken *unverified* AI-generated test.
        tests = state["tests"]
        failing = {r.index for r in report.failures()}
        bad = {i for i in analysis.invalid_tests
               if i in failing and 0 <= i < len(tests) and tests[i].validation == "unverified"}
        if bad:
            update["tests"] = [t for i, t in enumerate(tests) if i not in bad]
            update["pruned_tests"] = [{"index": i, **tests[i].model_dump()} for i in sorted(bad)]
            update["retest"] = True
            update["events"].append(event("analyze", f"discarded {len(bad)} unverified test(s) judged invalid; re-running"))
        return update

    @node("repair")
    async def repair(self, state):
        best = state["best"]
        code, calls = await self.repairer.repair(
            state["problem"], state["plan"], best["code"], best["report"], state.get("analysis"),
            history="\n".join(state.get("repair_history", [])[-3:]),
        )
        n = state.get("repair_attempts", 0) + 1
        return {
            "solution": code, "solution_origin": "repair", "solution_model": calls[-1].model,
            "repair_attempts": n,
            "trace": [c.to_dict() for c in calls],
            "events": [event("repair", f"repair attempt {n}/{state['max_repairs']}", model=calls[-1].model)],
        }

    @node("replan", fatal=True)
    async def replan(self, state):
        report: ExecutionReport = state["best"]["report"]
        analysis = state.get("analysis")
        feedback = f"Previous algorithm: {state['plan'].algorithm}\n{fmt_failures(report)}"
        if analysis:
            feedback += f"\nDiagnosis: {analysis.root_cause}"
        self.reward(state.get("plan_model"), "planning", report.pass_rate)
        plan, calls = await self.planner.plan(state["problem"], feedback=feedback)
        # Keep the ground-truth samples from the first plan if the new one lost them.
        if not plan.sample_tests:
            plan.sample_tests = state["plan"].sample_tests
        code, solve_calls = await self.solver.solve(state["problem"], plan)
        n = state.get("replans", 0) + 1
        return {
            "plan": plan, "plan_model": calls[-1].model,
            "solution": code, "solution_origin": "replan", "solution_model": solve_calls[-1].model,
            "replans": n, "stagnation": 0,
            "trace": [c.to_dict() for c in calls + solve_calls],
            "events": [event("replan", f"new approach: {plan.algorithm} ({plan.time_complexity})")],
        }

    @node("review")
    async def review(self, state):
        best = state["best"]
        review, calls = await self.reviewer.review(state["problem"], state["plan"], best["code"], best["report"])
        score = composite_score(review, best["report"].pass_rate)
        review.overall_score = score
        review.recommendation = "ACCEPT" if score >= state["acceptance_score"] else "REVISE"
        return {
            "review": review, "score": score,
            "best": {**best, "score": score},
            "trace": [c.to_dict() for c in calls],
            "events": [event("review", f"score {score}/100 -> {review.recommendation}", model=calls[-1].model)],
        }

    @node("refine")
    async def refine(self, state):
        best = state["best"]
        code, calls = await self.repairer.repair(
            state["problem"], state["plan"], best["code"], best["report"], review=state.get("review"),
        )
        n = state.get("refinements", 0) + 1
        return {
            "solution": code, "solution_origin": "refine", "solution_model": calls[-1].model,
            "refinements": n,
            "trace": [c.to_dict() for c in calls],
            "events": [event("refine", f"quality refinement {n}/{state['max_refinements']}")],
        }

    @node("finalize")
    async def finalize(self, state):
        best = state.get("best") or {}
        report: ExecutionReport | None = best.get("report")
        if state.get("fatal"):
            status = "error"
        elif not state.get("tests"):
            status = "no_tests"
        elif report and report.all_passed:
            status = "accepted" if state.get("score", 0) >= state["acceptance_score"] else "passed"
        else:
            status = "failed"
        if report:
            self.reward(state.get("plan_model"), "planning", report.pass_rate)
        final = {
            "status": status,
            "code": best.get("code", state.get("solution", "")),
            "version": best.get("version"),
            "passed": report.passed if report else 0,
            "total": report.total if report else 0,
            "score": state.get("score", 0),
            "repair_attempts": state.get("repair_attempts", 0),
            "replans": state.get("replans", 0),
            "refinements": state.get("refinements", 0),
        }
        return {
            "status": status, "final": final,
            "events": [event("finalize", f"{status}: best v{final['version']} "
                                         f"{final['passed']}/{final['total']} tests, score {final['score']}")],
        }
