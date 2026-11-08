"use client";

import type { PipelineEvent } from "@/lib/types";

const STAGES: { id: string; label: string; nodes: string[] }[] = [
  { id: "plan", label: "Plan", nodes: ["plan", "replan"] },
  { id: "build", label: "Write code and tests", nodes: ["solve", "generate_tests", "write_oracle"] },
  { id: "validate", label: "Validate tests", nodes: ["validate_tests"] },
  { id: "execute", label: "Execute", nodes: ["execute"] },
  { id: "analyze", label: "Analyze", nodes: ["analyze"] },
  { id: "repair", label: "Repair", nodes: ["repair", "refine"] },
  { id: "review", label: "Review", nodes: ["review"] },
  { id: "finalize", label: "Finalize", nodes: ["finalize"] },
];

export function PipelineStrip({ visits, current, running }: {
  visits: Record<string, number>;
  current: string | null;
  running: boolean;
}) {
  return (
    <ol className="pipeline" aria-label="Pipeline stages">
      {STAGES.map((stage) => {
        // The build stage runs its three agents in parallel, so count rounds rather than nodes.
        const count = stage.id === "build"
          ? Math.max(0, ...stage.nodes.map((id) => visits[id] || 0))
          : stage.nodes.reduce((n, id) => n + (visits[id] || 0), 0);
        const active = running && current !== null && stage.nodes.includes(current);
        const state = active ? "active" : count ? "done" : "idle";
        return (
          <li key={stage.id} className={`stage stage-${state}`}>
            <span className="stage-dot" aria-hidden />
            <span className="stage-label">{stage.label}</span>
            {count > 1 && <span className="stage-count" title={`ran ${count} times`}>×{count}</span>}
          </li>
        );
      })}
    </ol>
  );
}

const NODE_NAMES: Record<string, string> = {
  plan: "Planner", replan: "Re-planner", solve: "Solver", generate_tests: "Tester",
  write_oracle: "Oracle", validate_tests: "Validator", execute: "Sandbox", analyze: "Analyzer",
  repair: "Repair", refine: "Refine", review: "Reviewer", finalize: "Finalize",
};

export function Timeline({ events, startedAt }: { events: PipelineEvent[]; startedAt: number | null }) {
  const shown = events.filter((e) => e.message !== "done");
  if (!shown.length) {
    return <p className="empty">Agent activity appears here as each step finishes.</p>;
  }
  return (
    <ul className="timeline">
      {shown.map((e, i) => (
        <li key={i} className={e.data && (e.data as { level?: string }).level === "error" ? "tl-error" : ""}>
          <span className="tl-time">{startedAt ? `${Math.max(0, e.ts - startedAt).toFixed(1)}s` : ""}</span>
          <span className="tl-node">{NODE_NAMES[e.node] || e.node}</span>
          <span className="tl-msg">{e.message}</span>
        </li>
      ))}
    </ul>
  );
}
