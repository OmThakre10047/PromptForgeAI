from app.engine.state import ProjectState
from backend.app.providers.router import ModelRouter
from app.agents.developer import Developer


class ProjectManager:
    """
    The ProjectManager is the central controller of PromptForge AI.

    It is responsible for:
    - Creating the project state
    - Assigning work to employees
    - Managing the workflow
    - Returning the updated state
    """

    def __init__(self):
        self.router = ModelRouter()

        # Employees
        self.developer = Developer(self.router)

    async def execute(self, problem: str) -> ProjectState:
        """
        Executes one iteration of the project workflow.

        Parameters
        ----------
        problem : str
            Competitive programming problem provided by the user.

        Returns
        -------
        ProjectState
            Updated project state after all employees finish.
        """

        print("=" * 60)
        print("🚀 PromptForge AI Started")
        print("=" * 60)

        state = ProjectState(problem=problem)

        print("\n📌 Assigning task to Developer...\n")

        state = await self.developer.work(state)

        print("\n✅ Developer finished.\n")

        print("=" * 60)
        print("🎉 Workflow Completed")
        print("=" * 60)

        return state