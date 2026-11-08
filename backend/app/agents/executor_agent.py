from app.models.execution_result import ExecutionResult
from app.utils.cpp_executor import execute_cpp


class ExecutorAgent:

    async def execute(self, code: str, test_cases: list[dict]) -> ExecutionResult:
        return execute_cpp(code, test_cases)