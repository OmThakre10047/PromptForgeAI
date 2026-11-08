import os
import re
import time
import tempfile
import subprocess

from app.models.execution_result import ExecutionResult


def normalize_cpp(code: str) -> str:
    text = code.strip()

    match = re.search(
        r"```(?:cpp)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return text

def execute_cpp(code: str, test_cases: list[dict]) -> ExecutionResult:

    with tempfile.TemporaryDirectory() as temp_dir:
        cpp_file = os.path.join(temp_dir, "solution.cpp")
        exe_file = os.path.join(temp_dir, "solution.exe")

        with open(cpp_file, "w", encoding="utf-8") as f:
            f.write(normalize_cpp(code))

        compile_start = time.perf_counter()

        compile_process = subprocess.run(
            [
                "g++",
                cpp_file,
                "-std=c++17",
                "-O2",
                "-o",
                exe_file,
            ],
            capture_output=True,
            text=True,
        )

        compile_time = time.perf_counter() - compile_start

        if compile_process.returncode != 0:
            return ExecutionResult(
                compiled=False,
                ran=False,
                stderr=compile_process.stderr,
                compile_time=round(compile_time, 3),
                exit_code=compile_process.returncode,
                total_tests=len(test_cases),
                passed_tests=0,
                test_outputs=[],
            )

        passed_tests = 0
        test_outputs = []

        for case in test_cases:
            run_start = time.perf_counter()

            run_process = subprocess.run(
                [exe_file],
                input=case["input"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            run_time = time.perf_counter() - run_start

            actual = run_process.stdout.strip()
            expected = case["expected_output"].strip()

            if actual == expected and run_process.returncode == 0:
                passed_tests += 1

            test_outputs.append(
                f"INPUT:\n{case['input']}\n"
                f"EXPECTED:\n{expected}\n"
                f"ACTUAL:\n{actual}\n"
                f"STDERR:\n{run_process.stderr}\n"
                f"RUN_TIME:{round(run_time, 3)}"
            )

        return ExecutionResult(
            compiled=True,
            ran=True,
            stdout="",
            stderr="",
            exit_code=0,
            compile_time=round(compile_time, 3),
            run_time=0.0,
            passed_tests=passed_tests,
            total_tests=len(test_cases),
            test_outputs=test_outputs,
        )