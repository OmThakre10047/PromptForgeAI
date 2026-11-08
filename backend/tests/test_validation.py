from app.execution.validation import dedupe, validate_tests
from app.schemas.models import TestCase

ORACLE = "a = list(map(int, open(0).read().split()))\nprint(sum(a[1:1 + a[0]]))\n"


def tc(i, o):
    return TestCase(input=i, expected_output=o)


async def test_trusted_oracle_verifies_and_corrects(settings):
    samples = [tc("2\n1 2", "3")]
    generated = [tc("3\n1 1 1", "3"), tc("2\n5 5", "11"), tc("2\n1  2", "3")]  # wrong one + duplicate of sample
    tests, report = await validate_tests(samples, generated, ORACLE, "python", settings)
    assert report.trusted and report.verified == 1 and report.corrected == 1
    assert report.duplicates_removed == 1
    corrected = next(t for t in tests if t.validation == "corrected")
    assert corrected.expected_output == "10" and "11" in corrected.note
    assert tests[0].validation == "ground_truth"


async def test_untrusted_oracle_leaves_tests_unverified(settings):
    bad_oracle = "print(0)\n"
    tests, report = await validate_tests([tc("2\n1 2", "3")], [tc("1\n4", "4")], bad_oracle, "python", settings)
    assert not report.trusted and report.unverified == 1
    assert tests[1].validation == "unverified" and tests[1].expected_output == "4"


async def test_without_samples_agreement_only(settings):
    tests, report = await validate_tests([], [tc("1\n4", "4"), tc("1\n4 ", "5")], ORACLE, "python", settings)
    # second test is a whitespace-duplicate input and gets removed
    assert report.verified == 1 and len(tests) == 1


async def test_disagreement_without_samples_is_flagged(settings):
    tests, report = await validate_tests([], [tc("1\n4", "5")], ORACLE, "python", settings)
    assert tests[0].validation == "unverified" and "disagrees" in tests[0].note


async def test_oracle_compile_failure(settings):
    tests, report = await validate_tests([], [tc("1", "1")], "def (:", "python", settings)
    assert report.available and not report.compiled and report.unverified == 1


def test_dedupe_ignores_whitespace():
    out, removed = dedupe([tc("1 2", "3"), tc(" 1   2 ", "3"), tc("", "")])
    assert len(out) == 1 and removed == 2
