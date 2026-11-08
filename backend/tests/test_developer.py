import asyncio

from app.engine.state import ProjectState
from app.providers.router import ProviderRouter
from app.agents.developer import DeveloperAgent


async def main():

    router = ProviderRouter()

    provider = router.get_provider()

    agent = DeveloperAgent(provider)

    state = ProjectState(
        task="Solve Two Sum using HashMap."
    )

    state = await agent.run(state)

    print()

    print("TASK")
    print(state.task)

    print()

    print("GENERATED SOLUTION")
    print(state.current_solution)

    print()

    print("HISTORY")
    print(state.history)


if __name__ == "__main__":
    asyncio.run(main())