import pytest

from app.schemas.models import FailureAnalysis, GeneratedTests, Plan
from app.utils.parsing import ParseError, extract_code, extract_json, parse_model


def test_extract_json_from_fenced_block_with_prose():
    text = 'Here you go:\n```json\n{"a": 1, "b": {"c": [1,2]}}\n```\nThanks!'
    assert extract_json(text) == {"a": 1, "b": {"c": [1, 2]}}


def test_extract_json_tolerates_trailing_commas_and_think_blocks():
    text = '<think>{"not": "this"} let me think</think>{"x": [1, 2,], "y": "}",}'
    assert extract_json(text) == {"x": [1, 2], "y": "}"}


def test_extract_json_raises_on_garbage():
    with pytest.raises(ParseError):
        extract_json('Sure! {"category": "Arrays", "algorithm": ')


def test_parse_model_with_aliases_and_coercion():
    tests = parse_model('{"hidden_tests": [{"input": [1, 2, 3], "expected_output": 6}]}',
                        GeneratedTests, aliases={"hidden_tests": "tests"})
    assert tests.tests[0].input == "3\n1 2 3"
    assert tests.tests[0].expected_output == "6"


def test_plan_coerces_lists_and_strings():
    plan = Plan.model_validate({"algorithm": ["a", "b"], "strategy": "s", "edge_cases": "empty"})
    assert plan.algorithm == "a\nb" and plan.edge_cases == ["empty"]


def test_failure_analysis_normalises_fields():
    fa = FailureAnalysis.model_validate({"category": "Wrong Answer", "root_cause": "r", "fix_strategy": "f",
                                         "confidence": 85, "invalid_tests": ["2", "x"]})
    assert fa.category == "wrong_answer" and fa.confidence == 0.85 and fa.invalid_tests == [2]


def test_extract_code_prefers_language_block():
    text = "Explanation\n```python\nprint(1)\n```\n```cpp\n#include <x>\nint main(){}\n```"
    assert extract_code(text, "cpp").startswith("#include")
    assert extract_code(text, "python") == "print(1)"


def test_extract_code_without_fences_strips_prose():
    assert extract_code("Here is the code:\n#include <bits/stdc++.h>\nint main(){}", "cpp").startswith("#include")


def test_extract_code_unterminated_fence():
    assert extract_code("```cpp\nint main(){return 0;}", "cpp") == "int main(){return 0;}"
