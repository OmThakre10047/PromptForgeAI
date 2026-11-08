"""Compile and run untrusted, AI-generated programs against test cases.

Isolation here is process-level: per-test wall-clock timeout, CPU/memory/
file-size rlimits, output truncation, a scratch working directory and a
killed process group on timeout. For stronger isolation run the backend in
the provided Docker image (no network, read-only filesystem).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, settings as default_settings
from app.execution.judge import outputs_match
from app.schemas.models import ExecutionReport, TestCase, TestResult

try:
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None


@dataclass
class RunOutcome:
    stdout: str
    stderr: str
    returncode: int | None
    timed_out: bool
    time_ms: float


def _limits(memory_mb: int, cpu_s: float, max_output: int):
    def apply():  # runs in the child before exec
        if resource is None:
            return
        mem = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        cpu = int(cpu_s) + 1
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (max_output * 4, max_output * 4))
        resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
    return apply


def _truncate(data: bytes, limit: int) -> str:
    text = data[:limit].decode("utf-8", errors="replace")
    if len(data) > limit:
        text += f"\n...[truncated {len(data) - limit} bytes]"
    return text


async def _run(cmd: list[str], stdin: str, cwd: str, timeout: float, cfg: Settings, limit: bool = True) -> RunOutcome:
    start = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=_limits(cfg.MEMORY_LIMIT_MB, timeout, cfg.MAX_OUTPUT_BYTES) if limit and os.name == "posix" else None,
        start_new_session=True,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8", "PYTHONHASHSEED": "0"},
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin.encode()), timeout=timeout)
        timed_out = False
    except asyncio.TimeoutError:
        try:
            os.killpg(proc.pid, 9)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        out, err = await proc.communicate()
        timed_out = True
    elapsed = (time.perf_counter() - start) * 1000
    return RunOutcome(
        stdout=_truncate(out, cfg.MAX_OUTPUT_BYTES),
        stderr=_truncate(err, 4000),
        returncode=proc.returncode,
        timed_out=timed_out,
        time_ms=round(elapsed, 2),
    )


class Program:
    """A compiled (or interpreted) program living in a temp directory."""

    def __init__(self, code: str, language: str, cfg: Settings = default_settings):
        if language not in ("cpp", "python"):
            raise ValueError(f"Unsupported language: {language}")
        self.code = code
        self.language = language
        self.cfg = cfg
        self.workdir = tempfile.mkdtemp(prefix="pf_")
        self.compiled = False
        self.compile_error = ""
        self.compile_time_ms = 0.0

    @property
    def command(self) -> list[str]:
        if self.language == "cpp":
            return [str(Path(self.workdir) / "solution")]
        return [sys.executable, "-I", "-S", str(Path(self.workdir) / "solution.py")]

    async def build(self) -> bool:
        if self.language == "python":
            src = Path(self.workdir) / "solution.py"
            src.write_text(self.code, encoding="utf-8")
            outcome = await _run([sys.executable, "-m", "py_compile", str(src)], "", self.workdir,
                                 self.cfg.COMPILE_TIMEOUT_S, self.cfg, limit=False)
        else:
            if not shutil.which("g++"):
                self.compile_error = "g++ not found on PATH"
                return False
            src = Path(self.workdir) / "solution.cpp"
            src.write_text(self.code, encoding="utf-8")
            outcome = await _run(
                ["g++", "-std=c++17", "-O2", "-pipe", "-o", "solution", "solution.cpp"],
                "", self.workdir, self.cfg.COMPILE_TIMEOUT_S, self.cfg, limit=False,
            )
        self.compile_time_ms = outcome.time_ms
        self.compiled = outcome.returncode == 0 and not outcome.timed_out
        if not self.compiled:
            self.compile_error = (outcome.stderr or "compilation timed out")[:4000]
        return self.compiled

    async def run(self, stdin: str, timeout: float | None = None) -> RunOutcome:
        return await _run(self.command, stdin, self.workdir, timeout or self.cfg.RUN_TIMEOUT_S, self.cfg)

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    async def __aenter__(self):
        await self.build()
        return self

    async def __aexit__(self, *exc):
        self.cleanup()


def classify(outcome: RunOutcome, expected: str) -> str:
    if outcome.timed_out:
        return "TLE"
    if outcome.returncode != 0:
        return "RE"
    return "AC" if outputs_match(outcome.stdout, expected) else "WA"


async def execute(
    code: str,
    tests: list[TestCase],
    language: str = "cpp",
    cfg: Settings = default_settings,
) -> ExecutionReport:
    """Compile `code` and run it against every test, concurrently."""
    async with Program(code, language, cfg) as program:
        if not program.compiled:
            return ExecutionReport(
                language=language,
                compiled=False,
                compile_error=program.compile_error,
                compile_time_ms=program.compile_time_ms,
                results=[
                    TestResult(index=i, input=t.input, expected=t.expected_output, verdict="CE",
                               source=t.source, validation=t.validation)
                    for i, t in enumerate(tests)
                ],
            )

        sem = asyncio.Semaphore(max(1, (os.cpu_count() or 2)))

        async def one(i: int, t: TestCase) -> TestResult:
            async with sem:
                outcome = await program.run(t.input)
            return TestResult(
                index=i,
                input=t.input,
                expected=t.expected_output,
                actual=outcome.stdout,
                stderr=outcome.stderr,
                verdict=classify(outcome, t.expected_output),
                time_ms=outcome.time_ms,
                source=t.source,
                validation=t.validation,
            )

        results = await asyncio.gather(*(one(i, t) for i, t in enumerate(tests)))
        return ExecutionReport(
            language=language,
            compiled=True,
            compile_time_ms=program.compile_time_ms,
            results=list(results),
        )
