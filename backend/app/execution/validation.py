"""Differential validation of AI-generated tests against a brute-force oracle.

LLM-written expected outputs are frequently wrong, and a wrong test sends the
repair loop chasing a bug that does not exist. So before any test is used:

1. The oracle (a deliberately simple, brute-force reference solution written
   by a separate agent) is calibrated on the ground-truth sample tests taken
   from the problem statement.
2. If it passes all of them it is *trusted*: generated tests it agrees with
   become `verified`, and tests where it disagrees are `corrected` to the
   oracle's output.
3. If it cannot be calibrated (no samples) agreement still verifies a test,
   but disagreements are left `unverified` and flagged.
4. Inputs on which the oracle times out (brute force on large inputs) stay
   `unverified`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import Settings, settings as default_settings
from app.execution.judge import outputs_match
from app.execution.sandbox import Program
from app.schemas.models import TestCase


class OracleReport(BaseModel):
    available: bool = False
    compiled: bool = False
    compile_error: str = ""
    trusted: bool = False
    reason: str = ""
    samples_passed: int = 0
    samples_total: int = 0
    verified: int = 0
    corrected: int = 0
    unverified: int = 0
    duplicates_removed: int = 0


def _norm(s: str) -> str:
    return " ".join(s.split())


def dedupe(tests: list[TestCase]) -> tuple[list[TestCase], int]:
    seen, out = set(), []
    for t in tests:
        key = _norm(t.input)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out, len(tests) - len(out)


async def validate_tests(
    samples: list[TestCase],
    generated: list[TestCase],
    oracle_code: str | None,
    language: str,
    cfg: Settings = default_settings,
) -> tuple[list[TestCase], OracleReport]:
    samples = [t.model_copy(update={"source": "sample", "validation": "ground_truth"}) for t in samples]
    all_tests, removed = dedupe(samples + [t.model_copy(update={"source": "generated"}) for t in generated])
    sample_keys = {_norm(t.input) for t in samples}
    report = OracleReport(duplicates_removed=removed, samples_total=len(samples))

    if not oracle_code:
        report.reason = "no oracle available"
        report.unverified = sum(t.source == "generated" for t in all_tests)
        return all_tests, report

    report.available = True
    program = Program(oracle_code, language, cfg)
    try:
        await program.build()
        report.compiled = program.compiled
        if not program.compiled:
            report.compile_error = program.compile_error[:1000]
            report.reason = "oracle failed to compile"
            report.unverified = sum(t.source == "generated" for t in all_tests)
            return all_tests, report

        # 1) Calibrate on ground truth.
        for t in all_tests:
            if t.source != "sample":
                continue
            out = await program.run(t.input, cfg.ORACLE_TIMEOUT_S)
            if not out.timed_out and out.returncode == 0 and outputs_match(out.stdout, t.expected_output):
                report.samples_passed += 1

        if report.samples_total == 0:
            report.trusted = False
            report.reason = "no sample tests to calibrate the oracle; agreement-only verification"
        elif report.samples_passed == report.samples_total:
            report.trusted = True
            report.reason = f"oracle passed {report.samples_passed}/{report.samples_total} sample tests"
        else:
            report.trusted = False
            report.reason = (f"oracle failed calibration ({report.samples_passed}/"
                             f"{report.samples_total} samples); generated tests left unverified")

        # 2) Cross-check generated tests.
        validated: list[TestCase] = []
        for t in all_tests:
            if t.source == "sample" or _norm(t.input) in sample_keys:
                validated.append(t)
                continue
            if report.samples_total and not report.trusted:
                validated.append(t.model_copy(update={"validation": "unverified", "note": "oracle untrusted"}))
                report.unverified += 1
                continue
            out = await program.run(t.input, cfg.ORACLE_TIMEOUT_S)
            if out.timed_out or out.returncode != 0:
                note = "oracle timed out" if out.timed_out else "oracle crashed on this input"
                validated.append(t.model_copy(update={"validation": "unverified", "note": note}))
                report.unverified += 1
            elif outputs_match(out.stdout, t.expected_output):
                validated.append(t.model_copy(update={"validation": "verified"}))
                report.verified += 1
            elif report.trusted:
                validated.append(t.model_copy(update={
                    "expected_output": out.stdout.strip(),
                    "validation": "corrected",
                    "note": f"tester expected {t.expected_output.strip()[:80]!r}; oracle says {out.stdout.strip()[:80]!r}",
                }))
                report.corrected += 1
            else:
                validated.append(t.model_copy(update={
                    "validation": "unverified",
                    "note": f"oracle disagrees (oracle output {out.stdout.strip()[:80]!r})",
                }))
                report.unverified += 1
        return validated, report
    finally:
        program.cleanup()


class TestSuiteSummary(BaseModel):
    total: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_validation: dict[str, int] = Field(default_factory=dict)


def summarize(tests: list[TestCase]) -> TestSuiteSummary:
    s = TestSuiteSummary(total=len(tests))
    for t in tests:
        s.by_source[t.source] = s.by_source.get(t.source, 0) + 1
        s.by_validation[t.validation] = s.by_validation.get(t.validation, 0) + 1
    return s
