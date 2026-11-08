import asyncio

from app.agents.repair_agent import RepairAgent


async def main():

    repair = RepairAgent()

    prompt = """
Problem:
Find maximum subarray sum.

Candidate Solution:
Uses O(n²) brute force.

Review Report:

{
  "overall_score": 55,
  "issues":[
      "Use Kadane's Algorithm.",
      "Improve explanation."
  ]
}
"""

    result = await repair.generate(user_prompt=prompt)

    print(result)


if __name__ == "__main__":
    asyncio.run(main())