import asyncio

from app.agents.planner_agent import PlannerAgent


async def main():

    planner = PlannerAgent()

    result = await planner.generate(
        user_prompt="""
You are given an array of integers.
Find the maximum subarray sum.
Explain the algorithm and its time complexity.
"""
    )

    print("\n" + "=" * 60)
    print("PromptForge Output")
    print("=" * 60)
    print(f"Agent    : {result['agent']}")
    print(f"Model    : {result['model']}")
    print(f"Latency  : {result['latency']} sec")
    print("-" * 60)
    print(result["response"])
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())