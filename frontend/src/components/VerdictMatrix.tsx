"use client";

import type { TestCase, Verdict } from "@/lib/types";

export interface MatrixRow {
  version: number;
  origin: string;
  model?: string;
  compiled: boolean;
  verdicts: Verdict[];
}

const LABEL: Record<Verdict, string> = {
  AC: "Accepted", WA: "Wrong answer", TLE: "Time limit", RE: "Runtime error", CE: "Compile error", SKIP: "Skipped",
};

export function VerdictMatrix({ rows, tests }: { rows: MatrixRow[]; tests: TestCase[] }) {
  if (!rows.length) {
    return (
      <p className="empty">
        Each code version becomes a row here, with one cell per test. Run a problem to watch failing cells turn green
        as the repair loop works.
      </p>
    );
  }
  const width = Math.max(...rows.map((r) => r.verdicts.length), tests.length);
  return (
    <div className="matrix-wrap">
      <table className="matrix">
        <thead>
          <tr>
            <th scope="col">Version</th>
            {Array.from({ length: width }, (_, i) => {
              const t = tests[i];
              return (
                <th key={i} scope="col" className={t ? `col-${t.validation}` : ""}
                    title={t ? `${t.source} test, ${t.validation.replace("_", " ")}` : undefined}>
                  {i}
                </th>
              );
            })}
            <th scope="col">Passed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const passed = r.verdicts.filter((v) => v === "AC").length;
            return (
              <tr key={r.version}>
                <th scope="row">
                  <span className="v-num">v{r.version}</span>
                  <span className="v-origin">{r.origin}</span>
                </th>
                {Array.from({ length: width }, (_, i) => {
                  const v = r.verdicts[i];
                  return (
                    <td key={i}>
                      {v && <span className={`cell cell-${v}`} title={`Test ${i}: ${LABEL[v]}`}>{v === "AC" ? "" : v}</span>}
                    </td>
                  );
                })}
                <td className="m-total">{r.compiled ? `${passed}/${r.verdicts.length}` : "compile error"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="legend">
        <span><i className="cell cell-AC" /> passed</span>
        <span><i className="cell cell-WA" /> wrong answer</span>
        <span><i className="cell cell-TLE" /> too slow</span>
        <span><i className="cell cell-RE" /> crashed</span>
        <span className="legend-sep">Column shading marks where the expected output came from: problem statement, oracle-verified, or unverified.</span>
      </p>
    </div>
  );
}
