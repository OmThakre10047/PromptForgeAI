"""LangGraph workflow wiring.

                      ┌──► solve ──────────┐
   START ──► plan ────┼──► generate_tests ─┼──► validate_tests ──► execute ◄─────────────┐
                      └──► write_oracle ───┘                         │                    │
                                                    all pass ┌───────┴────────┐ failures │
                                                             ▼                ▼          │
                                                          review           analyze ──────┤ (re-test after
                                                     ┌──────┴──────┐     ┌───┴───────┐   │  pruning bad tests)
                                              score ok        below bar  repair    replan│
                                                     ▼             ▼       │          │  │
                                                 finalize       refine ────┴──────────┴──┘
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings
from app.llm.service import LLMService
from app.pipeline.nodes import PipelineNodes
from app.pipeline.state import PipelineState


# ---------------------------------------------------------------- routing
def after_plan(state: PipelineState):
    if state.get("fatal"):
        return "finalize"
    return ["solve", "generate_tests", "write_oracle"]  # parallel fan-out


def after_validate(state: PipelineState) -> str:
    if state.get("fatal") or not state.get("tests"):
        return "finalize"
    return "execute"


def after_execute(state: PipelineState) -> str:
    report = state["execution"]
    if report.all_passed:
        return "review"
    if state.get("solution_origin") == "refine":
        return "finalize"  # refinement broke something: keep the previous best version
    budget_left = (state.get("repair_attempts", 0) < state["max_repairs"]
                   or state.get("replans", 0) < state["max_replans"])
    return "analyze" if budget_left else "finalize"


def after_analyze(state: PipelineState) -> str:
    if state.get("retest"):
        return "execute"
    analysis = state.get("analysis")
    can_repair = state.get("repair_attempts", 0) < state["max_repairs"]
    can_replan = state.get("replans", 0) < state["max_replans"]
    wants_replan = bool(analysis and analysis.needs_replan and analysis.confidence >= 0.5) \
        or state.get("stagnation", 0) >= 2
    if wants_replan and can_replan:
        return "replan"
    if can_repair:
        return "repair"
    if can_replan:
        return "replan"
    return "finalize"


def after_review(state: PipelineState) -> str:
    if state.get("score", 0) >= state["acceptance_score"]:
        return "finalize"
    if state.get("refinements", 0) < state["max_refinements"]:
        return "refine"
    return "finalize"


def after_replan(state: PipelineState) -> str:
    return "finalize" if state.get("fatal") else "execute"


# ------------------------------------------------------------------ build
def build_workflow(llm: LLMService, language: str, settings: Settings):
    n = PipelineNodes(llm, language, settings)
    g = StateGraph(PipelineState)

    g.add_node("plan", n.plan)
    g.add_node("solve", n.solve)
    g.add_node("generate_tests", n.generate_tests)
    g.add_node("write_oracle", n.write_oracle)
    g.add_node("validate_tests", n.validate_tests)
    g.add_node("execute", n.execute)
    g.add_node("analyze", n.analyze)
    g.add_node("repair", n.repair)
    g.add_node("replan", n.replan)
    g.add_node("review", n.review)
    g.add_node("refine", n.refine)
    g.add_node("finalize", n.finalize)

    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", after_plan, ["solve", "generate_tests", "write_oracle", "finalize"])
    g.add_edge(["solve", "generate_tests", "write_oracle"], "validate_tests")  # join
    g.add_conditional_edges("validate_tests", after_validate, ["execute", "finalize"])
    g.add_conditional_edges("execute", after_execute, ["review", "analyze", "finalize"])
    g.add_conditional_edges("analyze", after_analyze, ["execute", "repair", "replan", "finalize"])
    g.add_edge("repair", "execute")
    g.add_conditional_edges("replan", after_replan, ["execute", "finalize"])
    g.add_conditional_edges("review", after_review, ["refine", "finalize"])
    g.add_edge("refine", "execute")
    g.add_edge("finalize", END)

    return g.compile()
