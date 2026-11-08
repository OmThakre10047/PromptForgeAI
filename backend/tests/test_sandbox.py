import pytest

from app.execution.judge import outputs_match
from app.execution.sandbox import execute
from app.schemas.models import TestCase


def tc(i, o):
    return TestCase(input=i, expected_output=o)


@pytest.mark.parametrize("actual,expected,ok", [
    ("1 2\n3\n", "1 2 3", True),
    ("3.0000001", "3", False),       # int expected, float given: tokens differ
    ("0.3333333", "0.333333333", True),
    ("YES", "yes", True),
    ("10", "1", False),
    ("1 2", "1 2 3", False),
])
def test_outputs_match(actual, expected, ok):
    assert outputs_match(actual, expected) is ok


async def test_cpp_verdicts(settings):
    code = r"""
#include <bits/stdc++.h>
int main(){ long long a; std::cin >> a;
  if (a == 1) { while(true){} }
  if (a == 2) { int* p = nullptr; *p = 1; }
  std::cout << a * 2 << "\n"; }
"""
    report = await execute(code, [tc("5", "10"), tc("6", "13"), tc("1", "2"), tc("2", "4")], "cpp", settings)
    assert report.compiled
    assert [r.verdict for r in report.results] == ["AC", "WA", "TLE", "RE"]
    assert report.passed == 1 and report.total == 4 and not report.all_passed


async def test_cpp_compile_error(settings):
    report = await execute("int main( { return 0 }", [tc("1", "1")], "cpp", settings)
    assert not report.compiled and "error" in report.compile_error
    assert report.results[0].verdict == "CE" and report.verdict_counts["CE"] == 1


async def test_python_runs_and_reports_runtime_errors(settings):
    code = "a = int(input())\nprint(10 // a)\n"
    report = await execute(code, [tc("2", "5"), tc("0", "0")], "python", settings)
    assert [r.verdict for r in report.results] == ["AC", "RE"]
    assert "ZeroDivisionError" in report.results[1].stderr


async def test_python_syntax_error_is_compile_error(settings):
    report = await execute("def f(:\n", [tc("", "")], "python", settings)
    assert not report.compiled


async def test_output_is_truncated(settings):
    settings.MAX_OUTPUT_BYTES = 1000
    report = await execute("print('x' * 100000)", [tc("", "x")], "python", settings)
    assert "truncated" in report.results[0].actual
