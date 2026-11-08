from dataclasses import dataclass, field
from typing import List


@dataclass
class ProjectState:

    # =========================
    # USER INPUT
    # =========================

    task: str

    # =========================
    # PROMPTS
    # =========================

    developer_prompt: str = ""

    reviewer_prompt: str = ""

    tester_prompt: str = ""

    # =========================
    # OUTPUTS
    # =========================

    solutions: dict = field(default_factory=dict)

    review: str = ""

    reflection: str = ""

    # =========================
    # TESTING
    # =========================

    hidden_tests: List[str] = field(default_factory=list)

    test_results: List[str] = field(default_factory=list)

    # =========================
    # EXECUTION
    # =========================

    iteration: int = 0

    success: bool = False

    max_iterations: int = 6

    # =========================
    # LOGGING
    # =========================

    history: List[str] = field(default_factory=list)

    def log(self, message: str):
        self.history.append(message)

    def next_iteration(self):
        self.iteration += 1

    def mark_success(self):
        self.success = True