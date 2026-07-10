from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Solution:
    model: str
    code: str
    explanation: str
    language: str
    confidence: float = 0.0


@dataclass
class Review:
    reviewer: str
    target_model: str
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    score: float


@dataclass
class TestCase:
    input_data: str
    expected_output: Optional[str] = None
    generated_by: str = "system"


@dataclass
class ExecutionResult:
    passed: bool
    compilation_error: bool
    runtime_error: bool
    execution_time: float
    failed_testcase: Optional[TestCase] = None
    error_message: str = ""


@dataclass
class EngineState:
    # User Input
    problem: str

    # Current Prompt
    current_prompt: str = ""

    # Iteration Counter
    iteration: int = 0

    # AI Solutions
    solutions: List[Solution] = field(default_factory=list)

    # Reviews
    reviews: List[Review] = field(default_factory=list)

    # Hidden Tests
    hidden_tests: List[TestCase] = field(default_factory=list)

    # Execution
    execution_results: List[ExecutionResult] = field(default_factory=list)

    # Reflection History
    reflections: List[str] = field(default_factory=list)

    # Final Answer
    final_solution: Optional[Solution] = None

    # Engine Status
    solved: bool = False