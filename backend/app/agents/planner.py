from app.services.llm import generate_response

SYSTEM_PROMPT = """
You are a task planning AI.

Analyze the user's request and return:
- Intent
- Domain
- Estimated Difficulty
- Required output format
-Suggested next step

Be concise.
"""

def plan_task(user_input: str):
    return generate_response(SYSTEM_PROMPT, user_input)