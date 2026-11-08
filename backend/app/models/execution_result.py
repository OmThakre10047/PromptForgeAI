from pydantic import BaseModel


class ExecutionResult(BaseModel):
    compiled: bool
    ran: bool

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0

    compile_time: float = 0.0
    run_time: float = 0.0

    passed_tests: int = 0
    total_tests: int = 0
    test_outputs: list[str] = []