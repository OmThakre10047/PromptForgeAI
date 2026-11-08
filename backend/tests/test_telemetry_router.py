from app.llm.model import RuntimeModel
from app.llm.router import LLMRouter
from app.llm.telemetry import TelemetryStore


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def model(mid, **kw):
    base = dict(coding_score=8, reasoning_score=8, json_score=8, speed_score=8, quality_score=8, supports_json=True)
    base.update(kw)
    return RuntimeModel(id=mid, name=mid, provider="mock", **base)


def test_telemetry_records_and_persists(tmp_path):
    path = tmp_path / "t.json"
    store = TelemetryStore(path)
    store.record_success("m", "coding", 2.0)
    store.record_success("m", "coding", 4.0)
    store.record_failure("m", "coding", "rate_limit", "429")
    store.record_quality("m", "coding", ok=False)
    store.record_reward("m", "coding", 0.5)

    reloaded = TelemetryStore(path)
    s = reloaded.get("m")
    assert (s.calls, s.successes, s.failures) == (3, 2, 1)
    assert s.failure_kinds == {"rate_limit": 1}
    assert 2.0 < s.ewma_latency < 4.0
    assert s.tasks["coding"].quality_fail == 1 and s.tasks["coding"].reward_mean == 0.5
    snap = reloaded.snapshot()["m"]
    assert snap["p95_latency"] == 4.0 and snap["success_rate"] == 2 / 3


def test_corrupt_telemetry_file_is_ignored(tmp_path):
    path = tmp_path / "t.json"
    path.write_text("{not json")
    assert TelemetryStore(path).models == {}


def test_circuit_breaker_opens_and_recovers():
    clock = Clock()
    store = TelemetryStore(None, breaker_threshold=3, breaker_cooldown_s=10, clock=clock)
    for _ in range(3):
        store.record_failure("m", "coding")
    assert store.is_open("m")
    clock.t += 11
    assert not store.is_open("m")
    store.record_failure("m", "coding")  # 4th consecutive -> doubled cooldown
    assert store.get("m").cooldown_until - clock.t == 20
    store.record_success("m", "coding", 1.0)
    assert not store.is_open("m") and store.get("m").consecutive_failures == 0


def test_capability_profile_matches_task():
    coder = model("coder", coding_score=14, reasoning_score=6)
    thinker = model("thinker", coding_score=6, reasoning_score=14)
    router = LLMRouter(TelemetryStore(None), exploration=0)
    assert router.route([coder, thinker], "coding").chosen == "coder"
    assert router.route([coder, thinker], "analysis").chosen == "thinker"


def test_unreliable_model_is_demoted_and_breaker_excludes_it():
    store = TelemetryStore(None, breaker_threshold=3, breaker_cooldown_s=60)
    star = model("star", coding_score=13)
    steady = model("steady", coding_score=11)
    router = LLMRouter(store, exploration=0)
    assert router.route([star, steady], "coding").chosen == "star"

    for _ in range(3):
        store.record_failure("star", "coding", "error")
        store.record_success("steady", "coding", 3.0)
    decision = router.route([star, steady], "coding")
    assert decision.chosen == "steady"
    assert [c.model_id for c in decision.candidates] == ["steady"]  # star's breaker is open


def test_all_models_open_degrades_gracefully():
    store = TelemetryStore(None, breaker_threshold=1, breaker_cooldown_s=60)
    a, b = model("a"), model("b")
    store.record_failure("a", "coding")
    store.record_failure("b", "coding")
    assert len(LLMRouter(store).route([a, b], "coding").candidates) == 2


def test_downstream_reward_and_latency_shift_ranking():
    store = TelemetryStore(None)
    a, b = model("a"), model("b")
    router = LLMRouter(store, exploration=0)
    for _ in range(5):
        store.record_success("a", "repair", 25.0)
        store.record_reward("a", "repair", 0.1)   # repairs that do not fix anything
        store.record_success("b", "repair", 4.0)
        store.record_reward("b", "repair", 1.0)
    d = router.route([a, b], "repair")
    assert d.chosen == "b"
    top = d.candidates[0].breakdown
    assert top["quality"] > d.candidates[1].breakdown["quality"]
    assert top["latency"] > d.candidates[1].breakdown["latency"]


def test_exploration_bonus_favours_untried_models():
    store = TelemetryStore(None)
    tried, fresh = model("tried"), model("fresh")
    for _ in range(20):
        store.record_success("tried", "coding", 1.0)
    router = LLMRouter(store, exploration=0.1)
    assert router.score(fresh, "coding").breakdown["exploration"] > router.score(tried, "coding").breakdown["exploration"]


def test_static_strategy_ignores_telemetry():
    store = TelemetryStore(None)
    a, b = model("a", coding_score=12), model("b", coding_score=10)
    for _ in range(10):
        store.record_failure("a", "coding")
    assert LLMRouter(store, strategy="static").route([a, b], "coding").candidates[0].model_id == "a"


def test_disabled_and_non_text_models_are_filtered():
    m1 = model("m1")
    m2 = model("m2", disabled=True)
    m3 = model("m3", modality="text+image->text")
    assert LLMRouter(TelemetryStore(None)).route([m1, m2, m3], "coding").considered == 1
