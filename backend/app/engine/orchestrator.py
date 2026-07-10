from app.engine.state import EngineState


class Orchestrator:

    async def run(self, state: EngineState):

        print(f"Iteration {state.iteration}")

        return state