from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class EngineState:
    problem: str = ""
    prompt: str = ""
    iteration: int = 0
    solutions: List[Dict[str, Any]] = field(default_factory=list)
    reviews: List[Dict[str, Any]] = field(default_factory=list)
    hidden_tests: List[Dict[str, Any]] = field(default_factory=list)
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 0.0
    solved: bool = False