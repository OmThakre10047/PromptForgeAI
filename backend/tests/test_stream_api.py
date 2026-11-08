import asyncio
import httpx


async def main():

    async with httpx.AsyncClient(timeout=None) as client:

        async with client.stream(
            "POST",
            "http://127.0.0.1:8000/generate/stream",
            json={
                "problem": """
Given an array of integers,
find the maximum subarray sum.
Return C++ code.
""",
                "acceptance_score": 95,
            },
        ) as response:

            async for line in response.aiter_lines():

                if line.startswith("data:"):

                    print(line[5:].strip())


if __name__ == "__main__":
    asyncio.run(main())