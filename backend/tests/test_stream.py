import asyncio

from app.graph.workflow import workflow


async def main():

    initial_state = {
        "problem": """
Given an array of integers,
find the maximum subarray sum.
Return C++ code.
""",
        "plan": "",
        "solution": "",
        "review": {},
        "repair_attempts": 0,
        "trace": [],
    }

    async for event in workflow.astream(initial_state):

        print("=" * 60)
        print(event)


if __name__ == "__main__":
    asyncio.run(main())