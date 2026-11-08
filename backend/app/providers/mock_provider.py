from app.providers.base_provider import BaseProvider


class MockProvider(BaseProvider):

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:

        if "developer" in system_prompt.lower():

            return """
def solve():
    return "Mock Solution"
"""

        elif "reviewer" in system_prompt.lower():

            return "Code quality is acceptable but needs optimization."

        elif "tester" in system_prompt.lower():

            return """
Hidden Test 1: PASS
Hidden Test 2: FAIL
"""

        elif "judge" in system_prompt.lower():

            return "FAIL"

        elif "reflection" in system_prompt.lower():

            return "The algorithm fails for duplicate inputs."

        return "Mock Response"