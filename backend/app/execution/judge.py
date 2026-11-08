"""Output comparison used to decide AC vs WA."""

from __future__ import annotations

FLOAT_TOL = 1e-6


def _tok_equal(a: str, b: str) -> bool:
    if a == b:
        return True
    if a.lower() == b.lower() and a.isalpha():
        return True  # YES / yes / Yes
    try:
        fa, fb = float(a), float(b)
    except ValueError:
        return False
    if "." not in b and "e" not in b.lower():
        return False  # integer answers must match exactly
    return abs(fa - fb) <= FLOAT_TOL * max(1.0, abs(fb))


def outputs_match(actual: str, expected: str) -> bool:
    """Whitespace-insensitive, token-wise comparison with float tolerance."""
    a, e = actual.split(), expected.split()
    return len(a) == len(e) and all(_tok_equal(x, y) for x, y in zip(a, e))
