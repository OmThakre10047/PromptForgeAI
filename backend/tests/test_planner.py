import asyncio

from app.agents.planner_agent import PlannerAgent


async def main():

    planner = PlannerAgent()

    problem = """
Given an array of integers,
find the maximum subarray sum.
"""

    result = await planner.plan(problem)

    print("\n===== Planner Output =====")

    print("Category:", result.category)
    print("Difficulty:", result.difficulty)
    print("Algorithm:", result.algorithm)
    print("Time:", result.time_complexity)
    print("Space:", result.space_complexity)

    print("\nEdge Cases:")
    for edge in result.edge_cases:
        print("-", edge)

    print("\nStrategy:")
    print(result.strategy)

    

asyncio.run(main())