"""Base agent: wraps LLMService with structured-output handling and quality feedback.

Every agent call produces an `AgentCall` record (agent, task, model, latency,
attempts, routing decision) that the pipeline adds to the run trace. When a
model's output fails to parse into the requested schema the agent reports a
quality failure to telemetry (so the router learns) and retries on a
different model with a corrective instruction.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Type, TypeVar

from pydantic import BaseModel

from app.core.logger import get_logger
from app.llm.service import LLMResult, LLMService
from app.prompts.system import JSON_RETRY_SUFFIX
from app.utils.parsing import ParseError, extract_code, parse_model

T = TypeVar("T", bound=BaseModel)
log = get_logger("agent")


@dataclass
class AgentCall:
    agent: str
    task: str
    model: str
    provider: str
    latency: float
    ok: bool = True
    attempts: list[dict] = field(default_factory=list)
    routing: dict = field(default_factory=dict)
    note: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class BaseAgent:
    name: str = "agent"
    task: str = "general"
    prompt_fn: Callable[[str], str]

    def __init__(self, llm: LLMService, language: str = "cpp"):
        self.llm = llm
        self.language = language

    @property
    def system_prompt(self) -> str:
        return type(self).prompt_fn(self.language)

    def _call(self, result: LLMResult, ok: bool = True, note: str = "") -> AgentCall:
        return AgentCall(
            agent=self.name, task=self.task, model=result.model, provider=result.provider,
            latency=round(result.latency, 3), ok=ok, attempts=result.attempts,
            routing=result.routing, note=note,
        )

    async def ask_text(self, user_prompt: str) -> tuple[str, list[AgentCall]]:
        result = await self.llm.generate(self.system_prompt, user_prompt, task=self.task)
        return result.content, [self._call(result)]

    async def ask_json(self, user_prompt: str, schema: Type[T], max_attempts: int = 3,
                       aliases: dict[str, str] | None = None) -> tuple[T, list[AgentCall]]:
        calls: list[AgentCall] = []
        tried: set[str] = set()
        prompt = user_prompt
        last_error: Exception | None = None
        for _ in range(max_attempts):
            result = await self.llm.generate(self.system_prompt, prompt, task=self.task, exclude=tried)
            try:
                parsed = parse_model(result.content, schema, aliases)
            except ParseError as exc:
                last_error = exc
                self.llm.telemetry.record_quality(result.model, self.task, ok=False)
                calls.append(self._call(result, ok=False, note=f"unparseable output: {exc}"[:200]))
                log.info("[%s] %s produced invalid %s; retrying on another model",
                         self.name, result.model, schema.__name__)
                tried.add(result.model)
                prompt = user_prompt + JSON_RETRY_SUFFIX.format(error=str(exc)[:200])
                continue
            self.llm.telemetry.record_quality(result.model, self.task, ok=True)
            calls.append(self._call(result))
            return parsed, calls
        raise ParseError(f"{self.name}: no model produced valid {schema.__name__}: {last_error}")

    async def ask_code(self, user_prompt: str) -> tuple[str, list[AgentCall]]:
        result = await self.llm.generate(self.system_prompt, user_prompt, task=self.task)
        code = extract_code(result.content, self.language)
        looks_ok = len(code) > 20 and (("main" in code) if self.language == "cpp" else True)
        self.llm.telemetry.record_quality(result.model, self.task, ok=looks_ok)
        return code, [self._call(result, ok=looks_ok)]
