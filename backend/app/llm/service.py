"""LLMService: route -> call -> measure -> record, with automatic fallback."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.core.config import Settings, settings as default_settings
from app.core.logger import get_logger
from app.llm.catalog import ModelCatalog
from app.llm.providers.base import BaseProvider, ProviderError
from app.llm.router import LLMRouter, RoutingDecision
from app.llm.telemetry import TelemetryStore

log = get_logger("llm")


@dataclass
class LLMResult:
    content: str
    model: str
    provider: str
    task: str
    latency: float
    attempts: list[dict] = field(default_factory=list)
    routing: dict = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0


class AllModelsFailed(Exception):
    def __init__(self, task: str, attempts: list[dict]):
        self.attempts = attempts
        detail = "; ".join(f"{a['model']}: {a['error']}" for a in attempts) or "no eligible models"
        super().__init__(f"All candidate models failed for task '{task}': {detail}")


class LLMService:

    def __init__(
        self,
        settings: Settings = default_settings,
        catalog: ModelCatalog | None = None,
        telemetry: TelemetryStore | None = None,
        providers: dict[str, BaseProvider] | None = None,
    ):
        self.settings = settings
        self.catalog = catalog or ModelCatalog(settings)
        if not self.catalog.models:
            self.catalog.load()
        self.telemetry = telemetry or TelemetryStore(
            settings.telemetry_file,
            breaker_threshold=settings.CIRCUIT_BREAKER_THRESHOLD,
            breaker_cooldown_s=settings.CIRCUIT_BREAKER_COOLDOWN_S,
        )
        self.router = LLMRouter(
            self.telemetry,
            strategy=settings.ROUTING_STRATEGY,
            exploration=settings.ROUTER_EXPLORATION,
        )
        self.providers = providers if providers is not None else self._build_providers()

    def _build_providers(self) -> dict[str, BaseProvider]:
        from app.llm.providers.mock import MockProvider
        from app.llm.providers.openai_compatible import groq_provider, openrouter_provider

        providers: dict[str, BaseProvider] = {"mock": MockProvider()}
        if self.settings.OPENROUTER_API_KEY:
            providers["openrouter"] = openrouter_provider(self.settings.OPENROUTER_API_KEY, self.settings.LLM_TIMEOUT_S)
        if self.settings.GROQ_API_KEY:
            providers["groq"] = groq_provider(self.settings.GROQ_API_KEY, self.settings.LLM_TIMEOUT_S)
        return providers

    def route(self, task: str, exclude: set[str] | None = None) -> RoutingDecision:
        return self.router.route(self.catalog.models, task, top_k=self.settings.ROUTER_TOP_K, exclude=exclude)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        task: str = "general",
        exclude: set[str] | None = None,
        temperature: float = 0.2,
    ) -> LLMResult:
        decision = self.route(task, exclude)
        attempts: list[dict] = []

        for candidate in decision.candidates:
            provider = self.providers.get(candidate.provider)
            if provider is None:
                attempts.append({"model": candidate.model_id, "error": f"no provider '{candidate.provider}'"})
                continue

            start = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    provider.generate(
                        model=candidate.model_id,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=self.settings.LLM_MAX_TOKENS,
                        temperature=temperature,
                    ),
                    timeout=self.settings.LLM_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                self.telemetry.record_failure(candidate.model_id, task, "timeout", "timed out")
                attempts.append({"model": candidate.model_id, "error": "timeout"})
                log.warning("[%s] %s timed out", task, candidate.model_id)
                continue
            except ProviderError as exc:
                self.telemetry.record_failure(candidate.model_id, task, exc.kind, str(exc))
                attempts.append({"model": candidate.model_id, "error": f"{exc.kind}: {exc}"[:200]})
                log.warning("[%s] %s failed: %s", task, candidate.model_id, exc)
                continue
            except Exception as exc:  # network errors, SDK errors, ...
                self.telemetry.record_failure(candidate.model_id, task, "error", repr(exc))
                attempts.append({"model": candidate.model_id, "error": repr(exc)[:200]})
                log.warning("[%s] %s errored: %r", task, candidate.model_id, exc)
                continue

            latency = time.perf_counter() - start
            self.telemetry.record_success(candidate.model_id, task, latency)
            attempts.append({"model": candidate.model_id, "error": None, "latency": round(latency, 3)})
            log.info("[%s] %s ok in %.2fs", task, candidate.model_id, latency)
            return LLMResult(
                content=response.content,
                model=candidate.model_id,
                provider=candidate.provider,
                task=task,
                latency=latency,
                attempts=attempts,
                routing=decision.to_dict(),
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )

        raise AllModelsFailed(task, attempts)
