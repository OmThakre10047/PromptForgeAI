"""Persistent, per-model and per-task telemetry that drives LLM routing.

Signals recorded for every model:
  * availability   - calls / successes / failures (by kind: error, rate_limit, timeout, empty)
  * latency        - EWMA plus a rolling window for p50/p95
  * output quality - did the response parse into the schema the agent asked for?
  * reward         - downstream outcome of the work, e.g. the test pass-rate of
                     code the model wrote, or whether its repair improved things
  * health         - consecutive failures + circuit-breaker cooldown
"""

from __future__ import annotations

import json
import os
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

LATENCY_WINDOW = 50
EWMA_ALPHA = 0.3


@dataclass
class TaskStats:
    calls: int = 0
    successes: int = 0
    quality_ok: int = 0
    quality_fail: int = 0
    reward_sum: float = 0.0
    reward_n: int = 0

    @property
    def reward_mean(self) -> float | None:
        return self.reward_sum / self.reward_n if self.reward_n else None


@dataclass
class ModelStats:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    failure_kinds: dict = field(default_factory=dict)
    ewma_latency: float | None = None
    latencies: deque = field(default_factory=lambda: deque(maxlen=LATENCY_WINDOW))
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    last_error: str = ""
    last_used: float = 0.0
    tasks: dict[str, TaskStats] = field(default_factory=dict)

    # ---- derived ----
    @property
    def success_rate(self) -> float | None:
        return self.successes / self.calls if self.calls else None

    @property
    def p50_latency(self) -> float | None:
        return statistics.median(self.latencies) if self.latencies else None

    @property
    def p95_latency(self) -> float | None:
        if not self.latencies:
            return None
        ordered = sorted(self.latencies)
        return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]

    def task(self, name: str) -> TaskStats:
        return self.tasks.setdefault(name, TaskStats())

    def to_dict(self) -> dict:
        return {
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "failure_kinds": self.failure_kinds,
            "ewma_latency": self.ewma_latency,
            "latencies": list(self.latencies),
            "consecutive_failures": self.consecutive_failures,
            "cooldown_until": self.cooldown_until,
            "last_error": self.last_error,
            "last_used": self.last_used,
            "tasks": {k: vars(v) for k, v in self.tasks.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelStats":
        stats = cls()
        for key in ("calls", "successes", "failures", "failure_kinds", "ewma_latency",
                    "consecutive_failures", "cooldown_until", "last_error", "last_used"):
            if key in data:
                setattr(stats, key, data[key])
        stats.latencies = deque(data.get("latencies", []), maxlen=LATENCY_WINDOW)
        stats.tasks = {k: TaskStats(**v) for k, v in data.get("tasks", {}).items()}
        return stats


class TelemetryStore:
    """Thread-safe telemetry with atomic JSON persistence."""

    def __init__(
        self,
        path: Path | None,
        breaker_threshold: int = 3,
        breaker_cooldown_s: float = 60.0,
        clock=time.time,
    ):
        self.path = path
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown_s = breaker_cooldown_s
        self.clock = clock
        self._lock = threading.RLock()
        self.models: dict[str, ModelStats] = {}
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.models = {
                k: ModelStats.from_dict(v)
                for k, v in raw.get("models", {}).items()
            }
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            # Corrupt/legacy file: start fresh rather than crash the router.
            self.models = {}

    def save(self) -> None:
        if not self.path:
            return
        with self._lock:
            payload = {"version": 2, "models": {k: v.to_dict() for k, v in self.models.items()}}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)

    def reset(self) -> None:
        with self._lock:
            self.models = {}
            self.save()

    # ------------------------------------------------------------- access
    def get(self, model_id: str) -> ModelStats:
        with self._lock:
            return self.models.setdefault(model_id, ModelStats())

    def peek(self, model_id: str) -> ModelStats | None:
        return self.models.get(model_id)

    def total_calls(self, task: str | None = None) -> int:
        with self._lock:
            if task is None:
                return sum(m.calls for m in self.models.values())
            return sum(m.tasks[task].calls for m in self.models.values() if task in m.tasks)

    def is_open(self, model_id: str) -> bool:
        """True when the circuit breaker is open (model cooling down)."""
        stats = self.models.get(model_id)
        return bool(stats and stats.cooldown_until > self.clock())

    # ------------------------------------------------------------ records
    def record_success(self, model_id: str, task: str, latency: float) -> None:
        with self._lock:
            s = self.get(model_id)
            s.calls += 1
            s.successes += 1
            s.consecutive_failures = 0
            s.cooldown_until = 0.0
            s.last_used = self.clock()
            s.latencies.append(round(latency, 3))
            s.ewma_latency = latency if s.ewma_latency is None else (
                EWMA_ALPHA * latency + (1 - EWMA_ALPHA) * s.ewma_latency
            )
            t = s.task(task)
            t.calls += 1
            t.successes += 1
            self.save()

    def record_failure(self, model_id: str, task: str, kind: str = "error", error: str = "") -> None:
        with self._lock:
            s = self.get(model_id)
            s.calls += 1
            s.failures += 1
            s.failure_kinds[kind] = s.failure_kinds.get(kind, 0) + 1
            s.consecutive_failures += 1
            s.last_error = error[:300]
            s.last_used = self.clock()
            if s.consecutive_failures >= self.breaker_threshold:
                # Exponential back-off, capped at 16x the base cooldown.
                exponent = min(s.consecutive_failures - self.breaker_threshold, 4)
                s.cooldown_until = self.clock() + self.breaker_cooldown_s * (2 ** exponent)
            # Rate limits are short-lived: always cool down briefly.
            if kind == "rate_limit":
                s.cooldown_until = max(s.cooldown_until, self.clock() + self.breaker_cooldown_s / 2)
            s.task(task).calls += 1
            self.save()

    def record_quality(self, model_id: str, task: str, ok: bool) -> None:
        """Whether the model's output satisfied the requested format/schema."""
        with self._lock:
            t = self.get(model_id).task(task)
            if ok:
                t.quality_ok += 1
            else:
                t.quality_fail += 1
            self.save()

    def record_reward(self, model_id: str, task: str, reward: float) -> None:
        """Downstream outcome in [0, 1] attributed to the model's work."""
        with self._lock:
            t = self.get(model_id).task(task)
            t.reward_sum += max(0.0, min(1.0, reward))
            t.reward_n += 1
            self.save()

    # ---------------------------------------------------------- reporting
    def snapshot(self) -> dict:
        with self._lock:
            now = self.clock()
            out = {}
            for model_id, s in self.models.items():
                out[model_id] = {
                    "calls": s.calls,
                    "successes": s.successes,
                    "failures": s.failures,
                    "failure_kinds": dict(s.failure_kinds),
                    "success_rate": s.success_rate,
                    "ewma_latency": s.ewma_latency,
                    "p50_latency": s.p50_latency,
                    "p95_latency": s.p95_latency,
                    "consecutive_failures": s.consecutive_failures,
                    "circuit_open": s.cooldown_until > now,
                    "cooldown_remaining_s": max(0.0, round(s.cooldown_until - now, 1)),
                    "last_error": s.last_error,
                    "tasks": {
                        name: {
                            "calls": t.calls,
                            "successes": t.successes,
                            "quality_ok": t.quality_ok,
                            "quality_fail": t.quality_fail,
                            "reward_mean": t.reward_mean,
                            "reward_n": t.reward_n,
                        }
                        for name, t in s.tasks.items()
                    },
                }
            return out
