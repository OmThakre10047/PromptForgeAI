"""Model catalog: discovers the models the router may choose from.

* OpenRouter - free text->text models discovered from the public model list
  (cached on disk so start-up works offline).
* Groq       - configured model ids (GROQ_MODELS).
* Mock       - simulated models with different strengths, latency and
               reliability, used for offline runs and the test-suite.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from app.core.config import Settings
from app.core.logger import get_logger
from app.llm.capability_scorer import CapabilityScorer
from app.llm.model import RuntimeModel

log = get_logger("catalog")

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

EXCLUDED_KEYWORDS = (
    "lyria", "music", "audio", "speech", "tts", "whisper", "image", "imagen", "video",
    "veo", "stable diffusion", "flux", "content safety", "safety model", "moderation",
    "guard", "embedding",
)


# ---------------------------------------------------------------- OpenRouter
def filter_free_text_models(models: list[dict]) -> list[dict]:
    kept = []
    for model in models:
        pricing = model.get("pricing", {})
        try:
            if float(pricing.get("prompt", 1)) != 0 or float(pricing.get("completion", 1)) != 0:
                continue
        except (TypeError, ValueError):
            continue
        if model.get("architecture", {}).get("modality", "") != "text->text":
            continue
        model_id = model.get("id", "").lower()
        text = f"{model_id} {model.get('name', '')} {model.get('description', '')}".lower()
        if any(k in text for k in EXCLUDED_KEYWORDS):
            continue
        if model_id in ("openrouter/free", "openrouter/auto"):
            continue  # random routers defeat telemetry attribution
        kept.append(model)
    return kept


def openrouter_to_runtime(models: list[dict]) -> list[RuntimeModel]:
    out = []
    for m in models:
        params = m.get("supported_parameters", []) or []
        rm = RuntimeModel(
            id=m["id"],
            name=m.get("name", m["id"]),
            provider="openrouter",
            context_length=m.get("context_length", 0) or 0,
            modality=m.get("architecture", {}).get("modality", "text->text"),
            supports_json="structured_outputs" in params or "response_format" in params,
            supports_tools="tools" in params,
            supports_reasoning="reasoning" in params or "reasoning_effort" in params,
            free=True,
        )
        out.append(CapabilityScorer.score(rm))
    return out


def load_openrouter_models(settings: Settings, refresh: bool = False) -> list[RuntimeModel]:
    cache: Path = settings.model_cache_file
    raw: list[dict] = []
    if cache.exists() and not refresh:
        try:
            raw = json.loads(cache.read_text(encoding="utf-8")).get("models", [])
        except json.JSONDecodeError:
            raw = []
    if not raw:
        try:
            resp = httpx.get(
                OPENROUTER_MODELS_URL,
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                timeout=30,
            )
            resp.raise_for_status()
            raw = filter_free_text_models(resp.json()["data"])
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"last_updated": time.time(), "models": raw}, indent=2), encoding="utf-8")
            log.info("Discovered %d free OpenRouter models", len(raw))
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("OpenRouter discovery failed (%s); no OpenRouter models loaded", exc)
            return []
    return openrouter_to_runtime(raw)


# ---------------------------------------------------------------------- Groq
def load_groq_models(settings: Settings) -> list[RuntimeModel]:
    models = []
    for model_id in [m.strip() for m in settings.GROQ_MODELS.split(",") if m.strip()]:
        rm = RuntimeModel(
            id=model_id,
            name=f"Groq: {model_id}",
            provider="groq",
            context_length=131072,
            supports_json=True,
            supports_tools=True,
            supports_reasoning=any(k in model_id for k in ("qwen3", "gpt-oss", "r1")),
        )
        rm = CapabilityScorer.score(rm)
        rm.speed_score += 4  # Groq LPUs are very fast
        models.append(rm)
    return models


# ---------------------------------------------------------------------- Mock
def mock_models() -> list[RuntimeModel]:
    """Simulated models whose behaviour is defined in providers/mock.py."""
    return [
        RuntimeModel(id="mock/reasoner-large", name="Mock Reasoner Large", provider="mock",
                     context_length=200_000, supports_json=True, supports_reasoning=True,
                     coding_score=10, reasoning_score=13, json_score=9, speed_score=4, quality_score=10),
        RuntimeModel(id="mock/coder-pro", name="Mock Coder Pro", provider="mock",
                     context_length=128_000, supports_json=True,
                     coding_score=13, reasoning_score=9, json_score=8, speed_score=7, quality_score=9),
        RuntimeModel(id="mock/flash-mini", name="Mock Flash Mini", provider="mock",
                     context_length=32_000, supports_json=True,
                     coding_score=6, reasoning_score=6, json_score=9, speed_score=12, quality_score=6),
        RuntimeModel(id="mock/flaky-giant", name="Mock Flaky Giant", provider="mock",
                     context_length=1_000_000, supports_json=True, supports_reasoning=True,
                     coding_score=14, reasoning_score=14, json_score=10, speed_score=6, quality_score=13),
    ]


class ModelCatalog:

    def __init__(self, settings: Settings):
        self.settings = settings
        self.models: list[RuntimeModel] = []

    def load(self) -> list[RuntimeModel]:
        if self.settings.mock_enabled:
            self.models = mock_models()
        else:
            models: list[RuntimeModel] = []
            if self.settings.OPENROUTER_API_KEY:
                models += load_openrouter_models(self.settings)
            if self.settings.GROQ_API_KEY:
                models += load_groq_models(self.settings)
            self.models = models
        log.info("Model catalog: %d models (%s)", len(self.models),
                 "mock" if self.settings.mock_enabled else "live")
        return self.models

    def refresh(self) -> list[RuntimeModel]:
        if not self.settings.mock_enabled and self.settings.OPENROUTER_API_KEY:
            load_openrouter_models(self.settings, refresh=True)
        return self.load()

    def get(self, model_id: str) -> RuntimeModel | None:
        return next((m for m in self.models if m.id == model_id), None)
