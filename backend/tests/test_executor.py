import asyncio

from app.agents.executor_agent import ExecutorAgent


code = r"""
#include <iostream>

int main() {
    std::cout << "Hello PromptForge";
    return 0;
}
"""


async def main():

    agent = ExecutorAgent()

    result = await agent.execute(code)

    print(result)


asyncio.run(main())