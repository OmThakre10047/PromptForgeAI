# Architecture notes

## Run lifecycle

1. `RunService` creates the initial `PipelineState` and compiles the LangGraph workflow for the requested language.
2. `plan` runs first. It is *fatal* on failure, because nothing downstream works without a plan.
3. `solve`, `generate_tests` and `write_oracle` run **in parallel**. Each returns a partial state update, and
   list-valued keys (`trace`, `events`, `versions`, `errors`, …) use `operator.add` reducers so concurrent writes merge.
4. `validate_tests` is the join node. It calibrates the oracle on the ground-truth samples and labels each test
   `ground_truth`, `verified`, `corrected` or `unverified`.
5. The loop `execute → analyze → repair/replan → execute` runs until every test passes or the budgets
   (`max_repairs`, `max_replans`) are used up.
6. `review` and an optional `refine` round enforce the quality bar. A refinement that breaks a test is discarded.
7. `finalize` always returns the **best** version (most tests passed; ties keep the earlier version), not the last one.

## Loop control (conditional edges)

| After | Condition | Next |
|---|---|---|
| `execute` | all tests pass | `review` |
| | a refinement broke something | `finalize` (keep previous best) |
| | budget left | `analyze` |
| `analyze` | an invalid unverified test was pruned | `execute` (re-test, no budget used) |
| | `needs_replan` (confidence ≥ 0.5) or 2 stagnant repairs, and a re-plan is left | `replan` |
| | repairs left | `repair` |
| `review` | score ≥ acceptance | `finalize` |
| | refinements left | `refine` |

## Failure handling

* Agent nodes are wrapped by the `@node` decorator. Exceptions become `errors` and `events`. Non-fatal nodes
  degrade: a missing oracle leaves tests unverified, a failed tester falls back to the sample tests only, a failed
  analyzer gets a heuristic diagnosis from the verdicts, and a failed reviewer uses neutral scores.
* `BaseAgent.ask_json` retries structured output on a *different* model (the previous one is excluded) with a
  corrective instruction, and records the quality failure so the router learns.
* `LLMService` walks the ranked fallback chain and records every failure kind (`timeout`, `rate_limit`, `empty`,
  `error`) in telemetry.

## Telemetry schema (`data/telemetry.json`)

```json
{
  "version": 2,
  "models": {
    "<model id>": {
      "calls": 0, "successes": 0, "failures": 0, "failure_kinds": {},
      "ewma_latency": null, "latencies": [], "consecutive_failures": 0, "cooldown_until": 0,
      "tasks": { "<task>": { "calls": 0, "successes": 0, "quality_ok": 0, "quality_fail": 0,
                             "reward_sum": 0.0, "reward_n": 0 } }
    }
  }
}
```

Writes are atomic (temporary file, then `os.replace`) and guarded by a lock.

## Sandbox limits

| Limit | Default | Setting |
|---|---|---|
| Wall clock per test | 2 s | `RUN_TIMEOUT_S` |
| Oracle wall clock per test | 4 s | `ORACLE_TIMEOUT_S` |
| Address space | 512 MB | `MEMORY_LIMIT_MB` |
| Captured stdout | 64 KB | `MAX_OUTPUT_BYTES` |
| Processes | 256 | (rlimit) |

Process-level limits are not a security boundary. In production, run the backend in the provided container
(read-only root filesystem, `no-new-privileges`, pid and memory caps) or behind gVisor/Firecracker.
