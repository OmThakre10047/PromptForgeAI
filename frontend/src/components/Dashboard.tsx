"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_URL, getJSON, streamSolve } from "@/lib/api";
import type { AgentCall, ExecutionReport, PipelineEvent, RunResult, StreamItem, TestCase, Verdict, Version } from "@/lib/types";
import { HistoryPanel, ModelsPanel, RoutingPanel, SolutionPanel, TestsPanel } from "./Panels";
import { PipelineStrip, Timeline } from "./Pipeline";
import { MatrixRow, VerdictMatrix } from "./VerdictMatrix";

const EXAMPLE = `Given an array of n integers, find the maximum sum of a non-empty contiguous subarray.

Input: the first line contains n (1 <= n <= 2*10^5). The second line contains n integers a_i (|a_i| <= 10^9).
Output: print the maximum subarray sum.

Example Input:
5
-2 1 -3 4 -1

Example Output:
4
`;

type Tab = "code" | "tests" | "routing" | "models" | "history";

interface Health { mock_mode: boolean; models: number; routing_strategy: string }

export default function Dashboard() {
  const [problem, setProblem] = useState(EXAMPLE);
  const [language, setLanguage] = useState<"cpp" | "python">("cpp");
  const [maxRepairs, setMaxRepairs] = useState(4);
  const [acceptance, setAcceptance] = useState(85);

  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [visits, setVisits] = useState<Record<string, number>>({});
  const [current, setCurrent] = useState<string | null>(null);
  const [rows, setRows] = useState<MatrixRow[]>([]);
  const [tests, setTests] = useState<TestCase[]>([]);
  const [trace, setTrace] = useState<AgentCall[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [tab, setTab] = useState<Tab>("code");
  const [refreshKey, setRefreshKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getJSON<Health>("/api/health").then(setHealth).catch(() => setHealthError(true));
  }, []);

  const reset = () => {
    setError(""); setEvents([]); setVisits({}); setCurrent(null); setRows([]); setTests([]);
    setTrace([]); setVersions([]); setResult(null);
  };

  const loadResult = useCallback((r: RunResult) => {
    setResult(r);
    setEvents(r.events);
    setStartedAt(r.events[0]?.ts ?? null);
    setTrace(r.trace);
    setVersions(r.versions);
    setTests(r.tests);
    setRows(r.versions.map((v) => ({
      version: v.version, origin: v.origin, model: v.model, compiled: v.compiled,
      verdicts: v.results?.length ? v.results : expandCounts(v.verdicts, v.total),
    })));
    const counts: Record<string, number> = {};
    r.events.filter((e) => e.message === "done").forEach((e) => { counts[e.node] = (counts[e.node] || 0) + 1; });
    setVisits(counts);
  }, []);

  const onItem = useCallback((item: StreamItem) => {
    if (item.type === "start") {
      setStartedAt(Date.now() / 1000);
      setCurrent("plan");
      return;
    }
    if (item.type === "error") {
      setError(item.error || "The run failed.");
      return;
    }
    if (item.type === "result" && item.result) {
      setResult(item.result);
      setVersions(item.result.versions);
      setTests(item.result.tests);
      setRefreshKey((k) => k + 1);
      return;
    }
    if (item.type !== "node" || !item.node) return;
    const node = item.node;
    const update = item.update || {};
    setVisits((v) => ({ ...v, [node]: (v[node] || 0) + 1 }));
    setCurrent(nextNode(node, update));
    if (item.events?.length) setEvents((e) => [...e, ...item.events!]);
    if (item.trace?.length) setTrace((t) => [...t, ...item.trace!]);
    if (Array.isArray(update.tests)) setTests(update.tests as TestCase[]);
    const versionsUpdate = update.versions as Version[] | undefined;
    if (versionsUpdate?.length) setVersions((v) => [...v, ...versionsUpdate]);
    if (node === "execute" && update.execution) {
      const report = update.execution as ExecutionReport;
      const meta = versionsUpdate?.[0];
      setRows((r) => [...r, {
        version: (update.version as number) ?? r.length + 1,
        origin: meta?.origin ?? "",
        model: meta?.model,
        compiled: report.compiled,
        verdicts: report.results.map((t) => t.verdict),
      }]);
    }
  }, []);

  const run = async () => {
    reset();
    setRunning(true);
    setTab("code");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamSolve(
        { problem, language, max_repairs: maxRepairs, acceptance_score: acceptance },
        onItem,
        controller.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError(`Could not reach the backend at ${API_URL}. Start it with "uvicorn app.main:app" and try again. (${(e as Error).message})`);
      }
    } finally {
      setRunning(false);
      setCurrent(null);
    }
  };

  const final = result?.final;

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <span className="logo" aria-hidden>⟁</span>
          <span>PromptForge</span>
        </div>
        <p className="tagline">Agents plan, write, test and repair code until it passes.</p>
        <div className="status-pill" data-state={healthError ? "down" : health ? "up" : "pending"}>
          {healthError ? "Backend offline" : health
            ? `${health.models} models, ${health.routing_strategy} routing${health.mock_mode ? ", offline mock mode" : ""}`
            : "Connecting…"}
        </div>
      </header>

      <main className="grid">
        <section className="panel compose" aria-labelledby="compose-h">
          <h2 id="compose-h">Problem</h2>
          <textarea value={problem} onChange={(e) => setProblem(e.target.value)} spellCheck={false}
                    aria-label="Problem statement" rows={16} />
          <p className="hint">Include example input and output if you have them: they become ground-truth tests.</p>
          <div className="controls">
            <label>Language
              <select value={language} onChange={(e) => setLanguage(e.target.value as "cpp" | "python")}>
                <option value="cpp">C++17</option>
                <option value="python">Python 3</option>
              </select>
            </label>
            <label>Repair attempts
              <input type="number" min={0} max={10} value={maxRepairs} onChange={(e) => setMaxRepairs(+e.target.value)} />
            </label>
            <label>Quality bar
              <input type="number" min={0} max={100} value={acceptance} onChange={(e) => setAcceptance(+e.target.value)} />
            </label>
          </div>
          <div className="actions">
            {running
              ? <button className="primary" onClick={() => abortRef.current?.abort()}>Stop run</button>
              : <button className="primary" onClick={run} disabled={problem.trim().length < 10}>Solve problem</button>}
          </div>
          {error && <p className="error-text" role="alert">{error}</p>}
        </section>

        <section className="panel live" aria-labelledby="live-h">
          <h2 id="live-h">Pipeline</h2>
          <PipelineStrip visits={visits} current={current} running={running} />
          {final && (
            <div className={`outcome outcome-${final.status}`}>
              <strong>{OUTCOME[final.status] || final.status}</strong>
              <span>
                {final.passed} of {final.total} tests passed, quality {final.score}/100, {final.repair_attempts} repair(s)
                {final.replans ? `, ${final.replans} re-plan(s)` : ""}, {result?.metrics.llm_calls} LLM calls
                {result?.metrics.fallbacks ? `, ${result.metrics.fallbacks} model fallback(s)` : ""} in {result?.metrics.duration_s.toFixed(1)}s
              </span>
            </div>
          )}
          <Timeline events={events} startedAt={startedAt} />
        </section>

        <section className="panel wide" aria-labelledby="matrix-h">
          <h2 id="matrix-h">Test results by version</h2>
          <VerdictMatrix rows={rows} tests={tests} />
        </section>

        <section className="panel wide">
          <div className="tabs" role="tablist">
            {([
              ["code", "Code"], ["tests", `Tests${tests.length ? ` (${tests.length})` : ""}`],
              ["routing", "Model routing"], ["models", "Models & telemetry"], ["history", "History"],
            ] as [Tab, string][]).map(([id, label]) => (
              <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>
            ))}
          </div>
          <div className="tab-body">
            {tab === "code" && <SolutionPanel versions={versions} finalVersion={final?.version} />}
            {tab === "tests" && <TestsPanel tests={tests} pruned={result?.pruned_tests || []} oracle={result?.oracle_report || null} />}
            {tab === "routing" && <RoutingPanel trace={trace} />}
            {tab === "models" && <ModelsPanel refreshKey={refreshKey} />}
            {tab === "history" && <HistoryPanel refreshKey={refreshKey} onOpen={(r) => { loadResult(r); setTab("code"); }} />}
          </div>
        </section>
      </main>
    </div>
  );
}

const OUTCOME: Record<string, string> = {
  accepted: "Accepted",
  passed: "Passes all tests, below the quality bar",
  failed: "Could not fix every test",
  no_tests: "No tests could be produced",
  error: "Run failed",
};

function nextNode(node: string, update: Record<string, unknown>): string | null {
  switch (node) {
    case "plan": return "solve";
    case "solve": case "generate_tests": case "write_oracle": return "validate_tests";
    case "validate_tests": return "execute";
    case "execute": return "analyze";
    case "analyze": return update.retest ? "execute" : "repair";
    case "repair": case "refine": case "replan": return "execute";
    case "review": return "finalize";
    default: return null;
  }
}

function expandCounts(counts: Record<string, number>, total: number): Verdict[] {
  const out: Verdict[] = [];
  (["AC", "WA", "TLE", "RE", "CE"] as Verdict[]).forEach((v) => { for (let i = 0; i < (counts[v] || 0); i++) out.push(v); });
  return out.slice(0, Math.max(total, 1));
}
