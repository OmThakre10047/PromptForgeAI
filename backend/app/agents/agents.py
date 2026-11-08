"""The PromptForge agent team.

Planner  -> designs the algorithm and extracts ground-truth samples
Solver   -> writes the solution
Tester   -> writes adversarial hidden tests
Oracle   -> writes a brute-force reference used to validate the tests
Analyzer -> diagnoses failures from execution evidence
Repair   -> applies targeted fixes
Reviewer -> scores quality once the tests pass
"""

from __future__ import annotations

from app.agents.base import AgentCall, BaseAgent
from app.prompts import system
from app.schemas.models import ExecutionReport, FailureAnalysis, GeneratedTests, Plan, Review, TestCase


def fmt_plan(plan: Plan) -> str:
    edge = "\n".join(f"- {e}" for e in plan.edge_cases) or "- (none listed)"
    return (
        f"Algorithm: {plan.algorithm}\n"
        f"Time complexity: {plan.time_complexity}\nSpace complexity: {plan.space_complexity}\n"
        f"Input format: {plan.input_format}\nOutput format: {plan.output_format}\n"
        f"Strategy:\n{plan.strategy}\n\nEdge cases:\n{edge}"
    )


def fmt_failures(report: ExecutionReport, limit: int = 4) -> str:
    if not report.compiled:
        return f"COMPILATION FAILED:\n{report.compile_error[:2500]}"
    lines = [f"Passed {report.passed}/{report.total} tests. Verdicts: {report.verdict_counts}"]
    for r in report.failures()[:limit]:
        lines.append(
            f"\n--- test #{r.index} [{r.verdict}] (source={r.source}, validation={r.validation}, {r.time_ms:.0f} ms)\n"
            f"input:\n{r.input[:600]}\nexpected:\n{r.expected[:300]}\nactual:\n{r.actual[:300]}"
            + (f"\nstderr:\n{r.stderr[:300]}" if r.stderr.strip() else "")
        )
    return "\n".join(lines)


class PlannerAgent(BaseAgent):
    name, task, prompt_fn = "planner", "planning", staticmethod(system.planner)

    async def plan(self, problem: str, feedback: str = "") -> tuple[Plan, list[AgentCall]]:
        prompt = f"PROBLEM:\n{problem}"
        if feedback:
            prompt += (
                "\n\nA PREVIOUS PLAN FAILED. Design a DIFFERENT, correct approach.\n"
                f"Failure report:\n{feedback}"
            )
        return await self.ask_json(prompt, Plan, aliases={"samples": "sample_tests", "examples": "sample_tests"})


class SolverAgent(BaseAgent):
    name, task, prompt_fn = "solver", "coding", staticmethod(system.solver)

    async def solve(self, problem: str, plan: Plan) -> tuple[str, list[AgentCall]]:
        return await self.ask_code(f"PROBLEM:\n{problem}\n\nPLAN:\n{fmt_plan(plan)}")


class TesterAgent(BaseAgent):
    name, task, prompt_fn = "tester", "testing", staticmethod(system.tester)

    async def generate_tests(self, problem: str, plan: Plan | None = None) -> tuple[list[TestCase], list[AgentCall]]:
        prompt = f"PROBLEM:\n{problem}"
        if plan:
            prompt += f"\n\nInput format: {plan.input_format}\nOutput format: {plan.output_format}\n" \
                      f"Known edge cases: {', '.join(plan.edge_cases)}"
        tests, calls = await self.ask_json(prompt, GeneratedTests,
                                           aliases={"hidden_tests": "tests", "test_cases": "tests"})
        return tests.tests, calls


class OracleAgent(BaseAgent):
    name, task, prompt_fn = "oracle", "oracle", staticmethod(system.oracle)

    async def reference(self, problem: str) -> tuple[str, list[AgentCall]]:
        return await self.ask_code(f"PROBLEM:\n{problem}")


class AnalyzerAgent(BaseAgent):
    name, task, prompt_fn = "analyzer", "analysis", staticmethod(system.analyzer)

    async def analyze(self, problem: str, plan: Plan, code: str, report: ExecutionReport,
                      history: str = "") -> tuple[FailureAnalysis, list[AgentCall]]:
        prompt = (
            f"PROBLEM:\n{problem}\n\nPLAN:\n{fmt_plan(plan)}\n\nCODE:\n```\n{code}\n```\n\n"
            f"EXECUTION:\n{fmt_failures(report)}"
        )
        if history:
            prompt += f"\n\nPREVIOUS REPAIR ATTEMPTS:\n{history}"
        return await self.ask_json(prompt, FailureAnalysis)


class RepairAgent(BaseAgent):
    name, task, prompt_fn = "repair", "repair", staticmethod(system.repair)

    async def repair(self, problem: str, plan: Plan, code: str, report: ExecutionReport | None,
                     analysis: FailureAnalysis | None = None, review: Review | None = None,
                     history: str = "") -> tuple[str, list[AgentCall]]:
        parts = [f"PROBLEM:\n{problem}", f"PLAN:\n{fmt_plan(plan)}", f"CURRENT CODE:\n```\n{code}\n```"]
        if report is not None and not report.all_passed:
            parts.append(f"FAILING TESTS:\n{fmt_failures(report)}")
        if analysis:
            parts.append(
                f"DIAGNOSIS ({analysis.category}, confidence {analysis.confidence:.2f}):\n"
                f"Root cause: {analysis.root_cause}\nFix: {analysis.fix_strategy}"
            )
        if review:
            parts.append(
                "The code passes every test. Improve it per this review WITHOUT changing behaviour:\n"
                + "\n".join(f"- {i}" for i in review.issues + review.suggestions)
            )
        if history:
            parts.append(f"EARLIER ATTEMPTS THAT DID NOT WORK:\n{history}")
        return await self.ask_code("\n\n".join(parts))


class ReviewerAgent(BaseAgent):
    name, task, prompt_fn = "reviewer", "review", staticmethod(system.reviewer)

    async def review(self, problem: str, plan: Plan, code: str, report: ExecutionReport) -> tuple[Review, list[AgentCall]]:
        prompt = (
            f"PROBLEM:\n{problem}\n\nINTENDED COMPLEXITY: time {plan.time_complexity}, space {plan.space_complexity}\n\n"
            f"CODE:\n```\n{code}\n```\n\nEXECUTION: passed {report.passed}/{report.total} tests, "
            f"max runtime {report.max_time_ms:.0f} ms."
        )
        return await self.ask_json(prompt, Review)
