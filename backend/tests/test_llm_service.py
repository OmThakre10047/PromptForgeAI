import asyncio

import pytest

from app.agents.agents import PlannerAgent
from app.llm.catalog import ModelCatalog
from app.llm.model import RuntimeModel
from app.llm.providers.base import BaseProvider, ProviderError, ProviderResponse
from app.llm.service import AllModelsFailed, LLMService
from app.llm.telemetry import TelemetryStore


class ScriptedProvider(BaseProvider):
    def __init__(self, behaviour):
        self.behaviour = behaviour  # model_id -> callable or str
        self.calls = []

    async def generate(self, model, system_prompt, user_prompt, max_tokens=4096, temperature=0.2):
        self.calls.append(model)
        b = self.behaviour[model]
        if isinstance(b, Exception):
            raise b
        if b == "hang":
            await asyncio.sleep(10)
        return ProviderResponse(content=b)


def make_service(settings, behaviour, scores):
    catalog = ModelCatalog(settings)
    catalog.models = [
        RuntimeModel(id=m, name=m, provider="scripted", supports_json=True,
                     coding_score=s, reasoning_score=s, json_score=s, speed_score=5, quality_score=s)
        for m, s in scores.items()
    ]
    provider = ScriptedProvider(behaviour)
    svc = LLMService(settings, catalog=catalog, telemetry=TelemetryStore(None),
                     providers={"scripted": provider})
    return svc, provider


async def test_fallback_chain_records_telemetry(settings):
    svc, provider = make_service(settings, {
        "best": ProviderError("429", kind="rate_limit"),
        "second": "hello",
    }, {"best": 12, "second": 9})
    result = await svc.generate("sys", "user", task="coding")
    assert result.model == "second" and provider.calls == ["best", "second"]
    assert result.attempts[0]["error"].startswith("rate_limit")
    assert svc.telemetry.get("best").failure_kinds == {"rate_limit": 1}
    assert svc.telemetry.is_open("best")  # rate limits trigger a short cooldown
    assert result.routing["chosen"] == "best"


async def test_timeout_counts_as_failure(settings):
    settings.LLM_TIMEOUT_S = 0.05
    svc, _ = make_service(settings, {"slow": "hang", "fast": "ok"}, {"slow": 12, "fast": 9})
    result = await svc.generate("sys", "user", task="coding")
    assert result.model == "fast"
    assert svc.telemetry.get("slow").failure_kinds == {"timeout": 1}


async def test_all_models_failed(settings):
    svc, _ = make_service(settings, {"a": ProviderError("x"), "b": ProviderError("y")}, {"a": 10, "b": 9})
    with pytest.raises(AllModelsFailed) as exc:
        await svc.generate("sys", "user", task="coding")
    assert len(exc.value.attempts) == 2


async def test_agent_retries_invalid_json_on_another_model(settings):
    good = '{"algorithm": "Kadane", "strategy": "scan", "sample_tests": []}'
    svc, provider = make_service(settings, {"sloppy": "Sure! {broken", "careful": good},
                                 {"sloppy": 12, "careful": 9})
    plan, calls = await PlannerAgent(svc).plan("problem")
    assert plan.algorithm == "Kadane"
    assert [c.ok for c in calls] == [False, True]
    assert provider.calls == ["sloppy", "careful"]
    assert svc.telemetry.get("sloppy").tasks["planning"].quality_fail == 1
    assert svc.telemetry.get("careful").tasks["planning"].quality_ok == 1


def test_mock_catalog_loaded_when_no_keys(settings):
    svc = LLMService(settings)
    assert {m.provider for m in svc.catalog.models} == {"mock"}
    assert "mock" in svc.providers
