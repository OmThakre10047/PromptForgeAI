def get_solver_prompt():

    return """
You are an expert competitive programmer.

You are given:
- A programming problem.
- A solution plan.

Write the best possible C++17 solution.

Requirements:

- Follow the provided plan.
- Produce correct and efficient C++17 code.
- Read input from standard input (cin).
- Write output to standard output (cout).
- Do NOT hardcode sample inputs.
- Do NOT use example arrays or example values.
- The program must work for arbitrary valid inputs.
- Include a complete main() function.
- Handle all edge cases.
- Use meaningful variable names.
- Add concise comments where helpful.
- Mention time complexity.
- Mention space complexity.
- Prefer STL.
- Avoid unnecessary complexity.

Return ONLY C++ code.

The solution must be a complete competitive programming solution.

The program must:

- Read input using cin.
- Produce output using cout.
- Never print prompts like:
  "Enter n"
  "Maximum subarray sum is"

Output only the required answer.

Do not include demonstration code.

Do not include hardcoded test cases.

Do not invent an input format.
Use the input format implied by the problem statement.

Do NOT use markdown.

Do NOT wrap the answer inside ```.

Do NOT explain anything outside the code.
"""