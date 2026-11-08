import asyncio

from app.agents.solver_agent import SolverAgent

async def main():
    solver = SolverAgent()

    result = await solver.generate(
        user_prompt="""
Given an array of integers,
find the maximum subarray sum.

Return an explanation and C++ code.
"""
    )

    print(result)

if __name__ == "__main__":
    asyncio.run(main())