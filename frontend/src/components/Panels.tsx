"use client";

import { useEffect, useState } from "react";

import { getJSON, del } from "@/lib/api";
import type { AgentCall, Candidate, RunResult, TestCase, Version } from "@/lib/types";

/* ------------------------------------------------------------------ code */
export function SolutionPanel({ versions, finalVersion }: { versions: Version[]; finalVersion?: number }) {
  const [selected, setSelected] = useState<number | null>(null);
  const current = versions.find((v) => v.version === (selected ?? finalVersion)) || versions[versions.length - 1];
  const [copied, setCopied] = useState(false);
  if (!current) return <p className="empty">No code yet.</p>;
  return (
    <div>
      <div className="toolbar">
        <div className="seg" role="tablist" aria-label="Code versions">
          {versions.map((v) => (
            <button key={v.version} role="tab" aria-selected={v.version === current.version}
                    onClick={() => setSelected(v.version)}>
              v{v.version} {v.origin}
              {v.version === finalVersion && <span className="final-mark">final</span>}
            </button>
          ))}
        </div>
        <button className="ghost" onClick={() => {
          navigator.clipboard.writeText(current.code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
        }}>{copied ? "Copied" : "Copy code"}</button>
      </div>
      <p className="meta">
        Written by {current.model || "unknown model"}. {current.compiled ? `${current.passed} of ${current.total} tests passed.` : "Did not compile."}
      </p>
      <pre className="code"><code>{current.code}</code></pre>
    </div>
  );
}

/* ----------------------------------------------------------------- tests */
const VALIDATION_TEXT: Record<string, string> = {
  ground_truth: "From the problem statement",
  verified: "Oracle agrees",
  corrected: "Corrected by oracle",
  unverified: "Unverified",
};

export function TestsPanel({ tests, pruned, oracle }: {
  tests: TestCase[]; pruned: TestCase[]; oracle: Record<string, unknown> | null;
}) {
  if (!tests.length) return <p className="empty">Tests appear once the tester and oracle finish.</p>;
  return (
    <div>
      {oracle && (
        <p className="meta">
          Oracle {oracle.trusted ? "trusted" : "not trusted"}: {String(oracle.reason || "")}.
          {" "}{String(oracle.verified ?? 0)} verified, {String(oracle.corrected ?? 0)} corrected, {String(oracle.unverified ?? 0)} unverified.
        </p>
      )}
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>#</th><th>Input</th><th>Expected</th><th>Provenance</th></tr></thead>
          <tbody>
            {tests.map((t, i) => (
              <tr key={i}>
                <td>{i}</td>
                <td><pre>{t.input}</pre></td>
                <td><pre>{t.expected_output}</pre></td>
                <td>
                  <span className={`badge badge-${t.validation}`}>{VALIDATION_TEXT[t.validation]}</span>
                  {t.note && <div className="note">{t.note}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pruned.length > 0 && (
        <p className="meta">The analyzer discarded {pruned.length} unverified test(s) whose expected output it judged wrong.</p>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- routing */
const COMPONENTS = ["capability", "reliability", "latency", "quality"] as const;

function ScoreBars({ c }: { c: Candidate }) {
  return (
    <div className="bars" aria-label={`score breakdown for ${c.model_id}`}>
      {COMPONENTS.map((k) => (
        <span key={k} className="bar" title={`${k}: ${(c.breakdown[k] ?? 0).toFixed(2)}`}>
          <span className={`bar-fill bar-${k}`} style={{ width: `${Math.round((c.breakdown[k] ?? 0) * 100)}%` }} />
        </span>
      ))}
    </div>
  );
}

export function RoutingPanel({ trace }: { trace: AgentCall[] }) {
  if (!trace.length) return <p className="empty">Every LLM call and the router&apos;s ranking behind it shows up here.</p>;
  return (
    <div className="table-wrap">
      <table className="data routing">
        <thead>
          <tr><th>Agent</th><th>Model used</th><th>Latency</th><th>Router&apos;s ranking</th></tr>
        </thead>
        <tbody>
          {trace.map((c, i) => (
            <tr key={i} className={c.ok ? "" : "row-warn"}>
              <td>{c.agent}<div className="note">{c.task}</div></td>
              <td>
                {c.model}
                {c.attempts.length > 1 && (
                  <div className="note">fell back after {c.attempts.filter((a) => a.error).map((a) => a.model).join(", ")}</div>
                )}
                {!c.ok && <div className="note warn">{c.note}</div>}
              </td>
              <td className="num">{c.latency.toFixed(2)}s</td>
              <td>
                <ol className="ranking">
                  {c.routing.candidates.map((cand) => (
                    <li key={cand.model_id}>
                      <span className="rank-name">{cand.model_id}</span>
                      <span className="num">{cand.score.toFixed(3)}</span>
                      <ScoreBars c={cand} />
                    </li>
                  ))}
                </ol>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="legend">
        Bars, left to right: capability fit for the task, reliability, latency, output quality and downstream reward.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- models */
interface Ranked extends Candidate { model: { name?: string; supports_reasoning?: boolean } }
interface TelemetryRow {
  calls: number; success_rate: number | null; p50_latency: number | null; p95_latency: number | null;
  circuit_open: boolean; failure_kinds: Record<string, number>;
}

export function ModelsPanel({ refreshKey }: { refreshKey: number }) {
  const [task, setTask] = useState("coding");
  const [tasks, setTasks] = useState<string[]>([]);
  const [ranking, setRanking] = useState<Ranked[]>([]);
  const [telemetry, setTelemetry] = useState<Record<string, TelemetryRow>>({});
  const [error, setError] = useState("");
  const [bump, setBump] = useState(0);

  useEffect(() => {
    let live = true;
    Promise.all([
      getJSON<{ ranking: Ranked[]; tasks: string[] }>(`/api/models?task=${task}`),
      getJSON<Record<string, TelemetryRow>>("/api/telemetry"),
    ]).then(([m, t]) => {
      if (!live) return;
      setRanking(m.ranking); setTasks(m.tasks); setTelemetry(t); setError("");
    }).catch((e) => live && setError(String(e.message || e)));
    return () => { live = false; };
  }, [task, refreshKey, bump]);

  if (error) return <p className="error-text">Could not load models: {error}</p>;
  return (
    <div>
      <div className="toolbar">
        <label className="inline">
          Rank models for
          <select value={task} onChange={(e) => setTask(e.target.value)}>
            {tasks.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <button className="ghost" onClick={() => del("/api/telemetry").then(() => setBump((b) => b + 1))}>
          Reset telemetry
        </button>
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr><th>Model</th><th>Score</th><th>Breakdown</th><th>Calls</th><th>Success</th><th>p50 / p95</th><th>Health</th></tr>
          </thead>
          <tbody>
            {ranking.map((r) => {
              const t = telemetry[r.model_id];
              return (
                <tr key={r.model_id}>
                  <td>{r.model_id}{r.model?.supports_reasoning && <div className="note">reasoning</div>}</td>
                  <td className="num">{r.score.toFixed(3)}</td>
                  <td><ScoreBars c={r} /></td>
                  <td className="num">{t?.calls ?? 0}</td>
                  <td className="num">{t?.success_rate != null ? `${Math.round(t.success_rate * 100)}%` : "–"}</td>
                  <td className="num">
                    {t?.p50_latency != null ? `${t.p50_latency.toFixed(2)}s / ${(t.p95_latency ?? 0).toFixed(2)}s` : "–"}
                  </td>
                  <td>{t?.circuit_open ? <span className="badge badge-open">cooling down</span> : <span className="badge badge-ok">healthy</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- history */
interface RunRow { run_id: string; status: string; language: string; problem: string; created_at: number; passed: number; total: number; score: number; duration_s: number }

export function HistoryPanel({ refreshKey, onOpen }: { refreshKey: number; onOpen: (r: RunResult) => void }) {
  const [rows, setRows] = useState<RunRow[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    getJSON<RunRow[]>("/api/runs").then(setRows).catch((e) => setError(String(e.message || e)));
  }, [refreshKey]);
  if (error) return <p className="error-text">Could not load history: {error}</p>;
  if (!rows.length) return <p className="empty">Finished runs are saved here.</p>;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead><tr><th>When</th><th>Problem</th><th>Language</th><th>Result</th><th>Score</th><th>Time</th><th /></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.run_id}>
              <td className="num">{new Date(r.created_at * 1000).toLocaleString()}</td>
              <td className="clip">{r.problem}</td>
              <td>{r.language}</td>
              <td><span className={`badge status-${r.status}`}>{r.status}</span> {r.passed}/{r.total}</td>
              <td className="num">{r.score}</td>
              <td className="num">{r.duration_s?.toFixed(1)}s</td>
              <td><button className="ghost" onClick={() => getJSON<RunResult>(`/api/runs/${r.run_id}`).then(onOpen)}>Open</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
