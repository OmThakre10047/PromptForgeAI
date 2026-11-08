import json

import pytest

from app.llm.providers.mock import MockProvider
from app.pipeline.graph import after_analyze, after_execute, after_review
from app.schemas.models import ExecutionReport, FailureAnalysis, TestResult
from tests.conftest import PROBLEM


@pytest.mark.parametrize("language", ["cpp", "python"])
async def test_full_run_repairs_and_accepts(runs, language):
    result = await runs.run(PROBLEM, language=language)
    final = result["final"]
    assert result["status"] == "accepted"
    assert final["passed"] == final["total"] == 9
    assert final["repair_attempts"] == 1
    assert "first" in final["code"] or "values[0]" in final["code"]  # the repaired version won

    # oracle calibrated on the statement's sample and corrected the tester's wrong answer
    assert result["oracle_report"]["trusted"] is True
    assert result["oracle_report"]["corrected"] == 1
    assert any(t["validation"] == "ground_truth" for t in result["tests"])

    # v1 failed on all-negative arrays, v2 (repair) passed everything
    versions = result["versions"]
    assert [v["origin"] for v in versions] == ["solver", "repair"]
    assert versions[0]["passed"] < versions[0]["total"] and versions[1]["passed"] == versions[1]["total"]
    assert result["analysis"]["category"] == "edge_case"
    assert result["review"]["recommendation"] == "ACCEPT"

    agents = {c["agent"] for c in result["trace"]}
    assert agents == {"planner", "solver", "tester", "oracle", "analyzer", "repair", "reviewer"}
    assert all(c["routing"]["candidates"] for c in result["trace"])
    assert runs.history.get(result["run_id"])["status"] == "accepted"


async def test_routing_feedback_is_recorded(runs):
    await runs.run(PROBLEM)
    snap = runs.llm.telemetry.snapshot()
    rewarded = {task for stats in snap.values() for task, t in stats["tasks"].items() if t["reward_n"]}
    assert {"coding", "repair", "testing", "oracle", "analysis", "planning"} <= rewarded


async def test_no_repair_budget_fails_with_best_version(runs):
    result = await runs.run(PROBLEM, max_repairs=0, max_replans=0)
    assert result["status"] == "failed"
    assert result["final"]["passed"] == 7 and result["final"]["total"] == 9
    assert len(result["versions"]) == 1


class PruningProvider(MockProvider):
    """Oracle cannot compile (tests stay unverified); analyzer blames the bad generated test."""

    def _respond(self, role, lang, kind, prompt):
        if role == "oracle":
            return "```python\ndef broken(:\n```"
        if role == "analyzer":
            return json.dumps({"category": "edge_case", "root_cause": "best starts at 0",
                               "fix_strategy": "init with a[0]", "invalid_tests": [8], "confidence": 0.9})
        return super()._respond(role, lang, kind, prompt)


async def test_analyzer_can_discard_invalid_unverified_tests(runs):
    runs.llm.providers["mock"] = PruningProvider()
    result = await runs.run(PROBLEM, language="python")
    assert result["oracle_report"]["compiled"] is False
    assert [p["input"] for p in result["pruned_tests"]] == ["4\n5 -10 5 5"]
    assert result["status"] == "accepted" and result["final"]["total"] == 8
    assert [v["origin"] for v in result["versions"]] == ["solver", "retest", "repair"]


class ReplanProvider(MockProvider):
    def _respond(self, role, lang, kind, prompt):
        if role == "analyzer":
            return json.dumps({"category": "wrong_algorithm", "root_cause": "wrong idea",
                               "fix_strategy": "rethink", "needs_replan": True, "confidence": 0.9})
        return super()._respond(role, lang, kind, prompt)


async def test_replan_loop(runs):
    runs.llm.providers["mock"] = ReplanProvider()
    result = await runs.run(PROBLEM, max_replans=1)
    origins = [v["origin"] for v in result["versions"]]
    assert origins[:2] == ["solver", "replan"] and "repair" in origins
    assert result["final"]["replans"] == 1 and result["status"] == "accepted"


async def test_stream_emits_node_events_then_result(runs):
    events = [e async for e in runs.stream(PROBLEM)]
    assert events[0]["type"] == "start" and events[-1]["type"] == "result"
    nodes = [e["node"] for e in events if e["type"] == "node"]
    assert nodes[0] == "plan" and nodes[-1] == "finalize"
    assert {"solve", "generate_tests", "write_oracle"} <= set(nodes[1:4])
    json.dumps(events)  # everything is JSON serialisable


def _report(verdicts):
    return ExecutionReport(language="cpp", compiled=True, results=[
        TestResult(index=i, input="", expected="", verdict=v) for i, v in enumerate(verdicts)])


def test_routing_functions():
    base = {"max_repairs": 2, "max_replans": 1, "max_refinements": 1, "acceptance_score": 80}
    assert after_execute({**base, "execution": _report(["AC", "AC"])}) == "review"
    assert after_execute({**base, "execution": _report(["AC", "WA"])}) == "analyze"
    assert after_execute({**base, "execution": _report(["WA"]), "solution_origin": "refine"}) == "finalize"
    assert after_execute({**base, "execution": _report(["WA"]), "repair_attempts": 2, "replans": 1}) == "finalize"

    fa = FailureAnalysis(root_cause="", fix_strategy="", needs_replan=True, confidence=0.9)
    assert after_analyze({**base, "analysis": fa}) == "replan"
    assert after_analyze({**base, "analysis": fa, "replans": 1}) == "repair"
    assert after_analyze({**base, "analysis": None, "stagnation": 2}) == "replan"
    assert after_analyze({**base, "analysis": None, "repair_attempts": 2}) == "replan"
    assert after_analyze({**base, "retest": True}) == "execute"

    assert after_review({**base, "score": 90}) == "finalize"
    assert after_review({**base, "score": 50}) == "refine"
    assert after_review({**base, "score": 50, "refinements": 1}) == "finalize"
