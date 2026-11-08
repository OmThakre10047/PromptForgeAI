"""Telemetry-aware LLM routing engine.

For every agent call the router ranks all available models for the agent's
*task* and returns an explainable `RoutingDecision`. The ordered candidates are
used as a fallback chain by `LLMService`.

score = w_cap  * capability      task-weighted capability priors (coding, reasoning, ...)
      + w_rel  * reliability     Bayesian-smoothed success rate (global + per task)
      + w_lat  * latency         EWMA latency vs. the task's latency budget
      + w_qual * quality         schema-valid output rate + downstream reward per task
      + reasoning_bonus          tasks that need deliberate reasoning prefer reasoning models
      + exploration              UCB1 bonus so under-sampled models still get tried

Models whose circuit breaker is open are skipped unless nothing else is left.
The "static" strategy uses capability priors only (useful as an A/B baseline).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from app.llm.model import RuntimeModel
from app.llm.telemetry import TelemetryStore

# Capability weights per task (each row sums to 1).
TASK_PROFILES: dict[str, dict[str, float]] = {
    "planning": {"reasoning": 0.45, "json": 0.25, "quality": 0.20, "speed": 0.10, "coding": 0.00},
    "coding":   {"coding": 0.50, "reasoning": 0.25, "quality": 0.15, "speed": 0.10, "json": 0.00},
    "testing":  {"json": 0.35, "reasoning": 0.30, "coding": 0.15, "speed": 0.20, "quality": 0.00},
    "oracle":   {"coding": 0.45, "reasoning": 0.35, "speed": 0.20, "json": 0.00, "quality": 0.00},
    "analysis": {"reasoning": 0.55, "json": 0.25, "coding": 0.10, "speed": 0.10, "quality": 0.00},
    "review":   {"reasoning": 0.40, "json": 0.35, "quality": 0.15, "speed": 0.10, "coding": 0.00},
    "repair":   {"coding": 0.45, "reasoning": 0.40, "quality": 0.10, "speed": 0.05, "json": 0.00},
    "general":  {"reasoning": 0.30, "coding": 0.20, "quality": 0.20, "speed": 0.20, "json": 0.10},
}

# Seconds of latency at which the latency component drops to 0.5.
LATENCY_BUDGET_S = {
    "planning": 20, "coding": 30, "testing": 20, "oracle": 25,
    "analysis": 20, "review": 15, "repair": 30, "general": 20,
}

REASONING_TASKS = {"planning", "analysis", "repair"}
JSON_TASKS = {"planning", "testing", "analysis", "review"}

WEIGHTS = {"capability": 0.40, "reliability": 0.25, "latency": 0.15, "quality": 0.20}
CAPABILITY_CEILING = 15.0  # capability priors are clamped to [0, 15]


@dataclass
class ScoredCandidate:
    model_id: str
    provider: str
    score: float
    breakdown: dict[str, float]
    circuit_open: bool = False


@dataclass
class RoutingDecision:
    task: str
    strategy: str
    candidates: list[ScoredCandidate] = field(default_factory=list)
    considered: int = 0

    @property
    def chosen(self) -> str | None:
        return self.candidates[0].model_id if self.candidates else None

    def to_dict(self, limit: int = 5) -> dict:
        return {
            "task": self.task,
            "strategy": self.strategy,
            "considered": self.considered,
            "chosen": self.chosen,
            "candidates": [asdict(c) for c in self.candidates[:limit]],
        }


def _smoothed(successes: float, trials: float, prior_mean: float, prior_weight: float) -> float:
    """Beta-binomial posterior mean: shrinks small samples toward the prior."""
    return (successes + prior_mean * prior_weight) / (trials + prior_weight)


class LLMRouter:

    def __init__(
        self,
        telemetry: TelemetryStore,
        strategy: str = "adaptive",
        exploration: float = 0.08,
    ):
        self.telemetry = telemetry
        self.strategy = strategy
        self.exploration = exploration

    # ----------------------------------------------------------- components
    @staticmethod
    def capability(model: RuntimeModel, task: str) -> float:
        profile = TASK_PROFILES.get(task, TASK_PROFILES["general"])
        values = {
            "coding": model.coding_score,
            "reasoning": model.reasoning_score,
            "json": model.json_score,
            "speed": model.speed_score,
            "quality": model.quality_score,
        }
        raw = sum(w * max(0.0, min(values[k], CAPABILITY_CEILING)) for k, w in profile.items())
        return raw / CAPABILITY_CEILING

    def reliability(self, model: RuntimeModel, task: str) -> float:
        stats = self.telemetry.peek(model.id)
        if not stats or not stats.calls:
            return 0.75  # optimistic prior for unseen models
        global_rate = _smoothed(stats.successes, stats.calls, 0.75, 4)
        t = stats.tasks.get(task)
        if not t or not t.calls:
            return global_rate
        task_rate = _smoothed(t.successes, t.calls, global_rate, 3)
        return 0.5 * global_rate + 0.5 * task_rate

    def latency(self, model: RuntimeModel, task: str) -> float:
        stats = self.telemetry.peek(model.id)
        budget = LATENCY_BUDGET_S.get(task, 20)
        if not stats or stats.ewma_latency is None:
            # No measurements yet: neutral-optimistic prior shaped by the speed prior.
            return 0.6 + 0.35 * max(0.0, min(model.speed_score, 10.0)) / 10.0
        return budget / (budget + stats.ewma_latency)

    def quality(self, model: RuntimeModel, task: str) -> float:
        stats = self.telemetry.peek(model.id)
        t = stats.tasks.get(task) if stats else None
        if not t:
            return 0.6
        parts, weights = [], []
        q_n = t.quality_ok + t.quality_fail
        if q_n:
            parts.append(_smoothed(t.quality_ok, q_n, 0.7, 3))
            weights.append(1.0)
        if t.reward_n:
            parts.append(_smoothed(t.reward_sum, t.reward_n, 0.5, 2))
            weights.append(1.5)  # downstream outcomes matter more than formatting
        if not parts:
            return 0.6
        return sum(p * w for p, w in zip(parts, weights)) / sum(weights)

    def exploration_bonus(self, model: RuntimeModel, task: str) -> float:
        if self.exploration <= 0:
            return 0.0
        total = self.telemetry.total_calls(task)
        stats = self.telemetry.peek(model.id)
        n = stats.tasks[task].calls if stats and task in stats.tasks else 0
        return self.exploration * math.sqrt(math.log(total + 2) / (n + 1))

    # --------------------------------------------------------------- scoring
    def score(self, model: RuntimeModel, task: str) -> ScoredCandidate:
        cap = self.capability(model, task)

        if self.strategy == "static":
            breakdown = {"capability": round(cap, 4)}
            return ScoredCandidate(model.id, model.provider, round(cap, 4), breakdown)

        rel = self.reliability(model, task)
        lat = self.latency(model, task)
        qual = self.quality(model, task)
        reasoning_bonus = 0.05 if (task in REASONING_TASKS and model.supports_reasoning) else 0.0
        json_penalty = -0.03 if (task in JSON_TASKS and not model.supports_json) else 0.0
        explore = self.exploration_bonus(model, task)

        total = (
            WEIGHTS["capability"] * cap
            + WEIGHTS["reliability"] * rel
            + WEIGHTS["latency"] * lat
            + WEIGHTS["quality"] * qual
            + reasoning_bonus + json_penalty + explore
        )
        breakdown = {
            "capability": round(cap, 4),
            "reliability": round(rel, 4),
            "latency": round(lat, 4),
            "quality": round(qual, 4),
            "reasoning_bonus": reasoning_bonus,
            "json_penalty": json_penalty,
            "exploration": round(explore, 4),
        }
        return ScoredCandidate(
            model.id, model.provider, round(total, 4), breakdown,
            circuit_open=self.telemetry.is_open(model.id),
        )

    def route(
        self,
        models: list[RuntimeModel],
        task: str,
        top_k: int = 3,
        exclude: set[str] | None = None,
    ) -> RoutingDecision:
        exclude = exclude or set()
        eligible = [
            m for m in models
            if not m.disabled and m.modality == "text->text" and m.id not in exclude
        ]
        scored = sorted(
            (self.score(m, task) for m in eligible),
            key=lambda c: c.score,
            reverse=True,
        )
        healthy = [c for c in scored if not c.circuit_open]
        # If every model is cooling down, degrade gracefully instead of failing.
        chain = (healthy or scored)[:top_k]
        return RoutingDecision(task=task, strategy=self.strategy, candidates=chain, considered=len(eligible))

    def leaderboard(self, models: list[RuntimeModel], task: str) -> list[dict]:
        ranked = sorted((self.score(m, task) for m in models if not m.disabled), key=lambda c: c.score, reverse=True)
        return [asdict(c) for c in ranked]
