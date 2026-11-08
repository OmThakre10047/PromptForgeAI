from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.graph.nodes import planner_node, repair_node, reviewer_node, solver_node
from app.graph.router import review_router
from app.models.execution_result import ExecutionResult
from app.models.planner_result import PlannerResult
from app.models.review_result import ReviewResult

from app.graph.nodes import (
    planner_node,
    solver_node,
    tester_node,
    executor_node,
    reviewer_node,
    repair_node,
)
from app.models.test_case import TestCase

class GraphState(TypedDict):
    problem: str

    plan: PlannerResult
    solution: str
    solution_history: list[str]
    sample_tests: list
    hidden_tests: list[TestCase]
    execution: ExecutionResult
    execution_history: list[ExecutionResult]
    review: ReviewResult
    review_history: list[ReviewResult]

    repair_attempts: int
    trace: list

    acceptance_score: int
    final_status: str

    planner_model: str
    solver_model: str
    reviewer_model: str
    repair_model: str

    
    

builder = StateGraph(GraphState)

builder.add_node("planner", planner_node)
builder.add_node("solver", solver_node)
builder.add_node("tester", tester_node)
builder.add_node("executor", executor_node)
builder.add_node("reviewer", reviewer_node)
builder.add_node("repair", repair_node)

builder.set_entry_point("planner")

builder.add_edge("planner", "solver")
builder.add_edge("solver", "tester")
builder.add_edge("tester", "executor")
builder.add_edge("executor", "reviewer")

builder.add_conditional_edges(
    "reviewer",
    review_router,
    {
        "accept": END,
        "repair": "repair",
    },
)

builder.add_edge("repair", "executor")

workflow = builder.compile()