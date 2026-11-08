from app.agents.planner_agent import PlannerAgent

planner = PlannerAgent()
async def main():
    result = await planner.generate(
        user_prompt="""
Given an array of integers,
find the maximum subarray sum.
"""
)

    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())