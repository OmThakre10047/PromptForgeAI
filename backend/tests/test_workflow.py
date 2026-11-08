import asyncio

from app.services.history_service import HistoryService
from app.services.workflow_service import WorkflowService

async def main():

    
    result = await WorkflowService.solve(
    """
Given an integer n followed by n integers,
find the maximum subarray sum.

Input
n
a1 a2 ... an

Output
Maximum subarray sum.
"""
)

    HistoryService.save(result)

    print("=" * 80)
    print("PLAN")
    print(result["plan"])

    print("=" * 80)
    print("SOLUTION")
    print(result["solution"])

    print("=" * 80)
    print("SOLUTION HISTORY")

    for i, solution in enumerate(result["solution_history"], 1):
        print(f"\n------ Version {i} ------\n")
        print(solution)

    print("=" * 80)
    print("EXECUTION")

    execution = result["execution"]

    print("Compiled :", execution.compiled)
    print("Ran       :", execution.ran)
    print("Exit Code :", execution.exit_code)
    print("Stdout")
    print(execution.stdout)

    print("Stderr")
    print(execution.stderr)

    print("=" * 80)
    print("EXECUTION HISTORY")

    for i, execution in enumerate(result["execution_history"], 1):
        print(f"\n------ Execution {i} ------")
        print(
            f"Passed: {execution.passed_tests}/{execution.total_tests}"
        )

    print("=" * 80)
    print("REVIEW")
    review = result["review"]

    print(review)

    print("\nReview History")

    for i, r in enumerate(result["review_history"], 1):
        print(
            f"{i}. "
            f"Score={r.overall_score} "
            f"Recommendation={r.recommendation}"
        )

    print("=" * 80)
    print("TRACE")

    print("=" * 80)
    print("FINAL STATUS")
    print(result["final_status"])

    for step in result["trace"]:
        print(step) 

if __name__ == "__main__":
    asyncio.run(main())