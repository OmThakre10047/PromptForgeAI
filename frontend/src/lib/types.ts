export type Verdict = "AC" | "WA" | "TLE" | "RE" | "CE" | "SKIP";

export interface TestCase {
  input: string;
  expected_output: string;
  source: "sample" | "generated";
  validation: "verified" | "corrected" | "unverified" | "ground_truth";
  note: string;
}

export interface TestResult {
  index: number;
  input: string;
  expected: string;
  actual: string;
  stderr: string;
  verdict: Verdict;
  time_ms: number;
  source: string;
  validation: string;
}

export interface ExecutionReport {
  language: string;
  compiled: boolean;
  compile_error: string;
  results: TestResult[];
  passed: number;
  total: number;
  pass_rate: number;
  verdicts: Record<string, number>;
  max_time_ms: number;
}

export interface Candidate {
  model_id: string;
  provider: string;
  score: number;
  breakdown: Record<string, number>;
  circuit_open: boolean;
}

export interface AgentCall {
  agent: string;
  task: string;
  model: string;
  provider: string;
  latency: number;
  ok: boolean;
  attempts: { model: string; error: string | null; latency?: number }[];
  routing: { task: string; strategy: string; chosen: string; considered: number; candidates: Candidate[] };
  note: string;
}

export interface PipelineEvent {
  node: string;
  message: string;
  ts: number;
  data?: Record<string, unknown>;
}

export interface Version {
  version: number;
  origin: string;
  model: string;
  passed: number;
  total: number;
  compiled: boolean;
  verdicts: Record<string, number>;
  results?: Verdict[];
  code: string;
}

export interface RunResult {
  run_id: string;
  problem: string;
  language: string;
  status: string;
  final: {
    status: string; code: string; version: number; passed: number; total: number;
    score: number; repair_attempts: number; replans: number; refinements: number;
  };
  plan: Record<string, unknown> | null;
  tests: TestCase[];
  pruned_tests: TestCase[];
  oracle_report: Record<string, unknown>;
  execution: ExecutionReport | null;
  analysis: Record<string, unknown> | null;
  review: Record<string, unknown> | null;
  versions: Version[];
  trace: AgentCall[];
  events: PipelineEvent[];
  errors: string[];
  metrics: {
    duration_s: number; llm_calls: number; llm_latency_s: number;
    fallbacks: number; models_used: Record<string, number>; versions: number;
  };
}

export interface StreamItem {
  type: "start" | "node" | "result" | "error";
  run_id?: string;
  mock?: boolean;
  node?: string;
  events?: PipelineEvent[];
  trace?: AgentCall[];
  update?: Record<string, unknown>;
  result?: RunResult;
  error?: string;
}
