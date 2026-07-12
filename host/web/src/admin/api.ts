/** admin/api.ts — fetch layer for the Pipeline Explorer console (admin server :8790 via the /admin/api Vite proxy).
 *  Shapes mirror admin/*.py (runs.summary, trace.build, ai_usage.report, ...) — kept loose (any) where the backend
 *  is still growing; every fetch surfaces {error} instead of throwing raw. */

export type RunSummary = {
  run_id: string; ts: string | null; ts_epoch: number | null; prompt: string | null;
  kind: string | null; page_key: string | null; page_title: string | null; metric: string | null;
  asset: string | null; asset_class: string | null; asset_how: string | null;
  ok: boolean | null; asset_pending: boolean | null; data_unavailable: boolean | null;
  degrade: any; multi_asset: boolean | null;
  cards: number | null; rendered: number | null; partial: number | null; blank: number | null;
  elapsed_ms: number | null; executions: number;
  n_failures: number; n_ai_calls: number; n_sql: number;
  prompt_tokens: number; completion_tokens: number;
  has: Record<string, boolean>;
};

export type TimelineRecord = { ts: string | null; stage: string; dur_ms: number | null; fields: Record<string, any> };
export type Execution = { execution: number; started: string | null; wall_ms: number | null; records: TimelineRecord[] };
export type AiCall = {
  idx: number; ts: string | null; execution: number | null; stage: string; model: string | null;
  ptok: number | null; ctok: number | null; ttok: number | null; finish: string | null;
  guided_json: boolean; sys_head: string; user_head: string; resp_head: string; req_chars: number;
};
export type SqlRow = {
  idx: number; ts: string | null; execution: number | null; db: string | null; sql: string;
  params: string | null; rows: number | null; ms: number | null; err: string | null;
};
export type FailureRow = {
  ts: string | null; execution: number | null; stage: string | null; card_id: number | null;
  reason: string | null; detail: string | null;
};
export type TraceCard = {
  card_id: number; render_card_id: number | null; title: string | null; endpoint: string | null;
  verdict: string | null; answerability: string | null; reason: string | null;
  leaf_stats: { real?: number; data?: number; undeclared?: number } | null; gaps: any[] | null;
  payload_error: any; fill_ok: boolean | null; fill_why: string | null;
  data_note: string | null; l2_answerability: string | null; validation_verdict: string | null;
  swap: boolean; asset: any;
};
export type Trace = {
  run_id: string; summary: RunSummary; timeline: Execution[]; ai_calls: AiCall[];
  sql: SqlRow[]; failures: FailureRow[]; notes: any; response: any;
};

const BASE = "/admin/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.error || `HTTP ${res.status}`);
  return body as T;
}

export const fetchRuns = (params: Record<string, string>) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "")).toString();
  return get<{ ok: boolean; total: number; runs: RunSummary[] }>(`/runs${qs ? `?${qs}` : ""}`);
};
export const fetchTrace = (rid: string) => get<{ ok: boolean; trace: Trace }>(`/run/${encodeURIComponent(rid)}`);
export const fetchAiCall = (rid: string, idx: number) => get<{ ok: boolean; call: any }>(`/run/${encodeURIComponent(rid)}/ai/${idx}`);
export const fetchRawResponse = (rid: string) => get<any>(`/run/${encodeURIComponent(rid)}/response`);
export const fetchHealth = () => get<any>(`/health`);
export const fetchExplorer = (qs = "") => get<any>(`/explorer${qs}`);
export const fetchLatency = (qs = "") => get<any>(`/latency${qs}`);
export const fetchCoverage = (qs = "") => get<any>(`/coverage${qs}`);
export const fetchUsage = (qs = "") => get<any>(`/ai-usage${qs}`);
export const fetchSql = (qs = "") => get<any>(`/sql${qs}`);
export const fetchFailures = (qs = "") => get<any>(`/failures${qs}`);
export const fetchValidation = (qs = "") => get<any>(`/validation${qs}`);
export const fetchAssetsLogQs = (qs = "") => get<any>(`/assets-log${qs}`);
export const searchPrompts = (qs = "") => get<{ ok: boolean; runs: RunSummary[] }>(`/search/prompts${qs}`);
export const searchErrors = (qs = "") => get<any>(`/search/errors${qs}`);
export const fetchReplays = () => get<any>(`/replays`);

export async function postReplay(body: { prompt: string; asset_id?: any; asset_ids?: any; date_window?: any }) {
  const res = await fetch(`${BASE}/replay`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const out = await res.json().catch(() => null);
  if (!res.ok) throw new Error(out?.error || `HTTP ${res.status}`);
  return out;
}
