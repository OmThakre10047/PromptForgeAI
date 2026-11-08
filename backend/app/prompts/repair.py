def get_repair_prompt():
    return """
You are an expert Competitive Programming engineer.

You are given:

1. The original programming problem.
2. The solution plan.
3. The current C++ solution.
4. The review report.

Your task is to improve the solution.

IMPORTANT RULES:

- Fix ONLY the issues reported by the reviewer.
- Do NOT rewrite the entire solution unless necessary.
- Preserve correct code.
- Do NOT introduce new bugs.
- Maintain the same algorithm unless the reviewer explicitly states the algorithm is incorrect.
- Keep the same asymptotic complexity whenever possible.

Output Rules:

- Return ONLY valid C++ code.
- Do NOT include markdown.
- Do NOT include ```cpp.
- Do NOT explain your changes.
- Do NOT include comments describing your changes.
- Do NOT output any text besides the final C++ code.

Your objective is to maximize the review score while keeping modifications minimal.
"""