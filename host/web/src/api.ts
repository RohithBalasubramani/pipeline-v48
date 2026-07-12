import type { PipelineResult, DateWindow, Candidate } from "./types";

// ── the ONE api module: every host/copilot endpoint the FE calls lives here with its response type. Components
//    consume these instead of inline fetch() literals, so an endpoint/shape change is a one-file edit. ──────────────

/** Build the Error to throw for a non-2xx response WITHOUT letting a non-JSON body (a reverse proxy's HTML 502) surface
 *  as a confusing SyntaxError: try the JSON {error}/{why} field, else fall back to the status line. Reads the body at
 *  most once — call it only on the !res.ok path (the caller reads res.json() itself on the ok path). */
async function httpError(res: Response): Promise<Error> {
  let msg = `HTTP ${res.status}`;
  try { const b = await res.json(); msg = b?.error || b?.why || msg; } catch { /* non-JSON body (e.g. a proxy HTML 502) — keep the status line */ }
  return new Error(msg);
}

/** GET /api/site — site identity + the LIVE dot (a REAL probe of the live-data DB connection). */
export type SiteStatus = { ok?: boolean; site?: string | null; live?: boolean | null };
export async function fetchSite(): Promise<SiteStatus> {
  const res = await fetch("/api/site");
  return (await res.json()) as SiteStatus;
}

/** GET /api/assets — the full pickable asset registry (same Candidate shape 1b serves). */
export async function fetchAssets(): Promise<Candidate[]> {
  const res = await fetch("/api/assets");
  const body = await res.json();
  return body?.ok && Array.isArray(body.assets) ? (body.assets as Candidate[]) : [];
}

/** POST /copilot/suggest — the typeahead completion for the prompt bar (caller owns abort/stale-guard). */
export type Suggest = { autofill: string; ghost: string; suggestions: string[]; latency_ms?: number };
export async function copilotSuggest(text: string, signal?: AbortSignal): Promise<Suggest> {
  const res = await fetch("/copilot/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    signal,
  });
  return (await res.json()) as Suggest;
}

/** GET /copilot/starters — the grounded suggested-command chips for the empty state. */
export type StarterChip = { tag: string; text: string };
export async function copilotStarters(): Promise<StarterChip[]> {
  const res = await fetch("/copilot/starters");
  const body = await res.json();
  return Array.isArray(body?.starters) ? (body.starters as StarterChip[]) : [];
}

// ── AI DECISION INSPECTOR (GET /api/inspector/*) — read-only views over the obs trace store ─────────────────────────

/** One execution in the inspector's left rail (obs_v_trace_summary row / trace-jsonl summary). */
export type InspectorTraceSummary = {
  trace_id: string;
  kind?: string | null;
  started_at?: string | number | null;
  latency_ms?: number | null;
  status?: string | null;
  prompt?: string | null;
  page_key?: string | null;
  n_cards?: number | null;
  n_llm_calls?: number | null;
  tokens_prompt?: number | null;
  tokens_completion?: number | null;
  source?: string | null;
};

/** The normalized decision semantics (obs/decision_view.py) of one LLM call. */
export type DecisionView = {
  kind?: string | null;                    // selection | classification | generative | unknown
  candidate_kind?: string | null;          // page_key | asset | column | swap_target | kind …
  candidates?: unknown[];
  candidates_total?: number | null;
  selected?: unknown;
  rejected?: unknown[];
  reasoning?: string | null;
  confidence?: number | boolean | null;
  error?: string | null;
};

/** One AI decision = one recorded LLM attempt with its full context. */
export type InspectorDecision = {
  i: number;
  stage?: string | null;
  card_id?: number | null;
  ts?: string | number | null;
  latency_ms?: number | null;
  model?: string | null;
  params?: { temperature?: number; seed?: number; response_format?: string; url?: string;
             timeout_s?: number; max_tokens?: number } | null;
  prompt_system?: string | null;
  prompt_user?: string | null;
  response?: string | null;
  tokens_prompt?: number | null;
  tokens_completion?: number | null;
  finish_reason?: string | null;
  attempt?: number | null;
  error_kind?: string | null;
  decision: DecisionView;
};

export type InspectorStage = {
  seq?: number | null; kind?: string | null; stage?: string | null; card_id?: number | null;
  latency_ms?: number | null; status?: string | null; n_llm_calls?: number | null;
  tokens_prompt?: number | null; tokens_completion?: number | null;
  confidence?: unknown; outputs?: unknown; errors?: unknown[] | null; warnings?: unknown[] | null;
};

export type InspectorTraceDetail = {
  trace: InspectorTraceSummary & Record<string, unknown>;
  stages: InspectorStage[];
  decisions: InspectorDecision[];
};

export async function fetchInspectorTraces(n = 50): Promise<InspectorTraceSummary[]> {
  const res = await fetch(`/api/inspector/traces?n=${n}`);
  if (!res.ok) throw await httpError(res);       // check res.ok BEFORE parsing — a proxy HTML 502 must not become a SyntaxError
  const body = await res.json();
  return Array.isArray(body?.traces) ? (body.traces as InspectorTraceSummary[]) : [];
}

export async function fetchInspectorTrace(traceId: string): Promise<InspectorTraceDetail> {
  const res = await fetch(`/api/inspector/trace?id=${encodeURIComponent(traceId)}`);
  if (!res.ok) throw await httpError(res);       // check res.ok BEFORE parsing — a proxy HTML 502 must not become a SyntaxError
  const body = await res.json();
  return body as InspectorTraceDetail;
}

export async function runPipeline(prompt: string, assetId?: number | string | Array<number | string> | null, dateWindow?: DateWindow | null, history?: Array<{ prompt: string; answer: string }> | null): Promise<PipelineResult> {
  // MULTI-ASSET: an ARRAY of ids → compare them in one run (asset_ids[]); a single id/none stays on asset_id.
  const ids = Array.isArray(assetId) ? assetId : null;
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // `history` = prior knowledge turns (oldest-first) so the one AI layer resolves follow-up questions in context.
    body: JSON.stringify({ prompt, asset_id: ids ? null : (assetId ?? null), asset_ids: ids, date_window: dateWindow ?? null, history: history ?? null }),
  });
  if (!res.ok) throw await httpError(res);        // check res.ok BEFORE parsing — a proxy HTML 502 must not become a SyntaxError
  const body = await res.json();
  return body as PipelineResult;
}

/** PER-CARD date re-fetch: a card's own CMD_V2 date control changed → re-COMPLETE JUST this card's payload for the new
 *  window via the same per-card NEURACT executor the page uses. Post the card's OWN payload as the metadata skeleton +
 *  its data_instructions + the server-served `refetch` bundle (asset_table / asset_name / member_scope / default) so the
 *  server can dispatch the right renderer (panel_aggregate member fan-out included). Returns the re-filled `payload`. */
export async function fetchCardFrame(card: any, dateWindow: DateWindow): Promise<any> {
  const res = await fetch("/api/frame", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exact_metadata: card?.payload,
      data_instructions: card?.data_instructions,
      refetch: card?.refetch,
      date_window: dateWindow,
    }),
  });
  if (!res.ok) throw await httpError(res);        // check res.ok BEFORE parsing — a proxy HTML 502 must not become a SyntaxError
  const body = await res.json();
  if (!body?.ok) throw new Error(body?.error || body?.why || `HTTP ${res.status}`);
  return body.payload;
}
