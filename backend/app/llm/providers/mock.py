"""Deterministic offline provider.

Simulates a pool of LLMs with different personalities so the whole platform
(routing, telemetry, test validation, repair loop) runs without API keys:

* mock/flaky-giant   - best capability priors, but fails 2 of every 3 calls
                       -> the router's reliability score + circuit breaker demote it
* mock/flash-mini    - fast, but returns malformed JSON for structured tasks
                       -> quality telemetry demotes it for JSON tasks
* mock/coder-pro / mock/reasoner-large - dependable

Agent behaviour is scripted for a few demo problems (maximum subarray sum,
sum of numbers). The first solution is intentionally buggy and one generated
test has a wrong expected output, so a run exercises oracle correction,
failure analysis and automatic repair.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict

from app.llm.providers.base import BaseProvider, ProviderError, ProviderResponse

LATENCY = {
    "mock/reasoner-large": 0.04,
    "mock/coder-pro": 0.02,
    "mock/flash-mini": 0.005,
    "mock/flaky-giant": 0.03,
}

# ------------------------------------------------------------- demo problems
KADANE_BUGGY = {
    "cpp": """#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    if (!(cin >> n)) return 0;
    long long best = 0, cur = 0;            // BUG: best should start at a[0]
    for (int i = 0; i < n; ++i) {
        long long x; cin >> x;
        cur = max(x, cur + x);
        best = max(best, cur);
    }
    cout << best << "\\n";
    return 0;
}
""",
    "python": """import sys

def main():
    data = sys.stdin.read().split()
    n = int(data[0])
    best = cur = 0  # BUG: best should start at a[0]
    for x in map(int, data[1:1 + n]):
        cur = max(x, cur + x)
        best = max(best, cur)
    print(best)

main()
""",
}

KADANE_FIXED = {
    "cpp": """#include <bits/stdc++.h>
using namespace std;

// Kadane's algorithm: O(n) time, O(1) extra space.
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    int n;
    if (!(cin >> n) || n <= 0) return 0;
    long long first;
    cin >> first;
    long long best = first, cur = first;    // handles all-negative arrays
    for (int i = 1; i < n; ++i) {
        long long x; cin >> x;
        cur = max(x, cur + x);
        best = max(best, cur);
    }
    cout << best << "\\n";
    return 0;
}
""",
    "python": """import sys

# Kadane's algorithm: O(n) time, O(1) extra space.
def main():
    data = sys.stdin.buffer.read().split()
    n = int(data[0])
    values = list(map(int, data[1:1 + n]))
    best = cur = values[0]  # handles all-negative arrays
    for x in values[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    print(best)

main()
""",
}

KADANE_ORACLE = {
    "cpp": """#include <bits/stdc++.h>
using namespace std;
int main() {
    int n; cin >> n;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;
    long long best = LLONG_MIN;
    for (int i = 0; i < n; ++i) {
        long long s = 0;
        for (int j = i; j < n; ++j) { s += a[j]; best = max(best, s); }
    }
    cout << best << endl;
}
""",
    "python": """n, *a = map(int, open(0).read().split())
a = a[:n]
print(max(sum(a[i:j + 1]) for i in range(n) for j in range(i, n)))
""",
}

KADANE_TESTS = [
    ("5\n1 2 3 4 5", "15"),
    ("1\n-7", "-7"),
    ("4\n-3 -1 -4 -2", "-1"),
    ("6\n2 -1 2 3 -9 4", "6"),
    ("3\n0 0 0", "0"),
    ("8\n-2 1 -3 4 -1 2 1 -5", "6"),
    ("5\n1000000000 1000000000 1000000000 -1 1000000000", "3999999999"),
    ("4\n5 -10 5 5", "11"),  # deliberately wrong (correct: 10) -> oracle corrects it
]

SUM_CODE = {
    "cpp": """#include <bits/stdc++.h>
using namespace std;
int main() {
    long long n, s = 0, x;
    if (!(cin >> n)) return 0;
    for (long long i = 0; i < n && (cin >> x); ++i) s += x;
    cout << s << "\\n";
}
""",
    "python": """import sys
d = sys.stdin.read().split()
n = int(d[0])
print(sum(map(int, d[1:1 + n])))
""",
}

SUM_TESTS = [("3\n1 2 3", "6"), ("1\n-5", "-5"), ("2\n1000000000 1000000000", "2000000000"), ("4\n0 0 0 0", "0")]


def _problem_kind(text: str) -> str:
    t = text.lower()
    if "subarray" in t or "kadane" in t:
        return "kadane"
    return "sum"


def _language(system_prompt: str) -> str:
    return "python" if "Python 3" in system_prompt else "cpp"


def _extract_samples(text: str) -> list[dict]:
    """Pull 'Input ... Output ...' example pairs out of a problem statement."""
    pattern = re.compile(
        r"(?:sample|example)\s*\d*\s*input\s*:?\s*\n(.*?)\n\s*(?:sample|example)?\s*\d*\s*output\s*:?\s*\n(.*?)(?:\n\s*\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return [{"input": i.strip(), "expected_output": o.strip()} for i, o in pattern.findall(text)]


def _fence(code: str, lang: str) -> str:
    return f"```{lang}\n{code}```"


class MockProvider(BaseProvider):
    name = "mock"

    def __init__(self):
        self.calls: dict[str, int] = defaultdict(int)

    async def generate(self, model, system_prompt, user_prompt, max_tokens=4096, temperature=0.2):
        self.calls[model] += 1
        await asyncio.sleep(LATENCY.get(model, 0.01))

        if model == "mock/flaky-giant" and self.calls[model] % 3 != 0:
            raise ProviderError("simulated upstream 503 from flaky provider", kind="error")

        role = system_prompt.strip().splitlines()[0].replace("ROLE:", "").strip().lower()
        lang = _language(system_prompt)
        kind = _problem_kind(user_prompt)
        json_role = role in {"planner", "tester", "analyzer", "reviewer"}

        if model == "mock/flash-mini" and json_role:
            return ProviderResponse(content="Sure! Here is the JSON: {\"category\": \"Arrays\", \"algorithm\": ")

        return ProviderResponse(content=self._respond(role, lang, kind, user_prompt), completion_tokens=200)

    # ------------------------------------------------------------- scripts
    def _respond(self, role: str, lang: str, kind: str, prompt: str) -> str:
        if role == "planner":
            samples = _extract_samples(prompt)
            if kind == "kadane":
                plan = {
                    "category": "Dynamic Programming", "difficulty": "Medium",
                    "algorithm": "Kadane's Algorithm",
                    "time_complexity": "O(n)", "space_complexity": "O(1)",
                    "input_format": "n, then n integers", "output_format": "a single integer",
                    "edge_cases": ["single element", "all negative values", "64-bit overflow", "zeros"],
                    "strategy": "Track the best sum ending at each index; answer is the max over all indices.",
                }
            else:
                plan = {
                    "category": "Math", "difficulty": "Easy", "algorithm": "Linear scan",
                    "time_complexity": "O(n)", "space_complexity": "O(1)",
                    "input_format": "n, then n integers", "output_format": "a single integer",
                    "edge_cases": ["overflow"], "strategy": "Accumulate in a 64-bit integer.",
                }
            plan["sample_tests"] = samples
            return json.dumps(plan)

        if role == "solver":
            return _fence((KADANE_BUGGY if kind == "kadane" else SUM_CODE)[lang], lang)

        if role == "oracle":
            return _fence((KADANE_ORACLE if kind == "kadane" else SUM_CODE)[lang], lang)

        if role == "tester":
            cases = KADANE_TESTS if kind == "kadane" else SUM_TESTS
            return json.dumps({"tests": [{"input": i, "expected_output": o} for i, o in cases]})

        if role == "analyzer":
            return json.dumps({
                "category": "edge_case",
                "root_cause": "The running maximum is initialised to 0, so arrays whose elements are all "
                              "negative report 0 instead of the largest (least negative) element.",
                "fix_strategy": "Initialise both the running sum and the best sum with the first element and "
                                "iterate from index 1.",
                "failing_tests_explained": ["all-negative inputs return 0"],
                "needs_replan": False,
                "invalid_tests": [],
                "confidence": 0.92,
            })

        if role == "repair":
            return _fence((KADANE_FIXED if kind == "kadane" else SUM_CODE)[lang], lang)

        if role == "reviewer":
            return json.dumps({
                "correctness": 100, "efficiency": 95, "edge_cases": 90,
                "code_quality": 88, "readability": 90,
                "issues": [], "suggestions": ["Consider documenting the input format at the top."],
            })

        return "OK"
