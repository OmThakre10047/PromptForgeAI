"""Typed contracts exchanged between agents, the sandbox and the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _stringify(value) -> str:
    if isinstance(value, list):
        # A bare list like [1, 2, 3] is most often "n then the values".
        if all(not isinstance(v, (list, dict)) for v in value):
            return f"{len(value)}\n" + " ".join(map(str, value))
        return "\n".join(_stringify(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


class TestCase(BaseModel):
    __test__ = False  # not a pytest class

    input: str
    expected_output: str
    source: Literal["sample", "generated"] = "generated"
    # verified: trusted oracle agreed | corrected: oracle overrode the tester
    # unverified: no trusted oracle output | ground_truth: from the problem statement
    validation: Literal["verified", "corrected", "unverified", "ground_truth"] = "unverified"
    note: str = ""

    @field_validator("input", "expected_output", mode="before")
    @classmethod
    def _to_str(cls, v):
        return _stringify(v)


class Plan(BaseModel):
    category: str = "General"
    difficulty: str = "Medium"
    algorithm: str
    time_complexity: str = ""
    space_complexity: str = ""
    edge_cases: list[str] = Field(default_factory=list)
    strategy: str
    input_format: str = ""
    output_format: str = ""
    sample_tests: list[TestCase] = Field(default_factory=list)

    @field_validator("edge_cases", mode="before")
    @classmethod
    def _edge_list(cls, v):
        if isinstance(v, str):
            return [v]
        return [str(x) if not isinstance(x, str) else x for x in (v or [])]

    @field_validator("strategy", "algorithm", mode="before")
    @classmethod
    def _join(cls, v):
        if isinstance(v, list):
            return "\n".join(map(str, v))
        return v


class GeneratedTests(BaseModel):
    tests: list[TestCase]


class FailureAnalysis(BaseModel):
    category: Literal[
        "compile_error", "runtime_error", "timeout", "wrong_answer",
        "edge_case", "wrong_algorithm", "io_format", "invalid_test", "other",
    ] = "other"
    root_cause: str
    fix_strategy: str
    failing_tests_explained: list[str] = Field(default_factory=list)
    needs_replan: bool = False
    # Indices of *unverified* tests the analyzer believes have a wrong expected output.
    invalid_tests: list[int] = Field(default_factory=list)
    confidence: float = 0.5

    @field_validator("invalid_tests", mode="before")
    @classmethod
    def _idx(cls, v):
        out = []
        for x in v or []:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        allowed = {"compile_error", "runtime_error", "timeout", "wrong_answer",
                   "edge_case", "wrong_algorithm", "io_format", "invalid_test", "other"}
        v = str(v or "other").strip().lower().replace(" ", "_").replace("-", "_")
        return v if v in allowed else "other"

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.5
        return v / 100 if v > 1 else max(0.0, v)


class Review(BaseModel):
    correctness: int = 0
    efficiency: int = 0
    edge_cases: int = 0
    code_quality: int = 0
    readability: int = 0
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    overall_score: int = 0
    recommendation: Literal["ACCEPT", "REVISE"] = "REVISE"

    @field_validator("correctness", "efficiency", "edge_cases", "code_quality", "readability", mode="before")
    @classmethod
    def _score(cls, v):
        try:
            return max(0, min(100, int(float(v))))
        except (TypeError, ValueError):
            return 0

    @field_validator("issues", "suggestions", mode="before")
    @classmethod
    def _issues(cls, v):
        out = []
        for item in v or []:
            if isinstance(item, dict):
                out.append(item.get("description") or item.get("message") or str(item))
            else:
                out.append(str(item))
        return out


Verdict = Literal["AC", "WA", "TLE", "RE", "CE", "SKIP"]


class TestResult(BaseModel):
    __test__ = False

    index: int
    input: str
    expected: str
    actual: str = ""
    stderr: str = ""
    verdict: Verdict
    time_ms: float = 0.0
    source: str = "generated"
    validation: str = "unverified"


class ExecutionReport(BaseModel):
    language: str
    compiled: bool
    compile_error: str = ""
    compile_time_ms: float = 0.0
    results: list[TestResult] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(r.verdict == "AC" for r in self.results)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def all_passed(self) -> bool:
        return self.compiled and self.total > 0 and self.passed == self.total

    @property
    def verdict_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.verdict] = counts.get(r.verdict, 0) + 1
        if not self.compiled:
            counts["CE"] = max(1, self.total)
        return counts

    @property
    def max_time_ms(self) -> float:
        return max((r.time_ms for r in self.results), default=0.0)

    def failures(self) -> list[TestResult]:
        return [r for r in self.results if r.verdict != "AC"]

    def summary(self) -> dict:
        return {
            "compiled": self.compiled,
            "passed": self.passed,
            "total": self.total,
            "pass_rate": round(self.pass_rate, 4),
            "verdicts": self.verdict_counts,
            "max_time_ms": round(self.max_time_ms, 1),
        }

    def to_api(self) -> dict:
        data = self.model_dump()
        data.update(self.summary())
        return data
