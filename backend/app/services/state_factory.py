class StateFactory:

    @staticmethod
    def create(problem: str, acceptance_score: int = 95):

        return {
            "problem": problem,

            "plan": "",
            "solution": "",

            "solution_history": [],

            "execution": {},
            "execution_history": [],

            "review": {},
            "review_history": [],

            "hidden_tests": [],

            "repair_attempts": 0,

            "trace": [],

            "acceptance_score": acceptance_score,

            "planner_model": "",
            "solver_model": "",
            "reviewer_model": "",
            "repair_model": "",

            "final_status": "",

            "sample_tests": [],
        }