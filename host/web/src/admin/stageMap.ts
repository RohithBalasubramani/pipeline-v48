/** admin/stageMap.ts — the Pipeline Explorer's NINE display stages and how every trace artifact is assigned to one.
 *
 *  The backend serves raw material (stage timeline records, AI calls, SQL reads, failure rows); this module folds it
 *  into the fixed pipeline story the console renders: Prompt → Knowledge Gate → Page Selection → Asset Resolution →
 *  Story Selection → Layer 2 → Executor → Validation → Renderer. Assignment vocabularies mirror the writers:
 *  obs/stage.py names, admin/ai_usage.py STAGE_MARKERS labels, obs/failures.py stage/reason values. */
import type { AiCall, Execution, FailureRow, SqlRow, TimelineRecord } from "./api";

export type StageKey =
  | "prompt" | "knowledge" | "page" | "asset" | "story" | "layer2" | "executor" | "validation" | "renderer";

export const STAGES: { key: StageKey; title: string; blurb: string }[] = [
  { key: "prompt", title: "Prompt", blurb: "the request as received (text, pinned asset, date window)" },
  { key: "knowledge", title: "Knowledge Gate", blurb: "one AI call routes dashboard / knowledge / off-scope (knowledge/ems.py)" },
  { key: "page", title: "Page Selection", blurb: "1a storytelling router picks the page template (layer1a/route.py) + reroutes" },
  { key: "asset", title: "Asset Resolution", blurb: "1b pure-AI asset pin / picker + column basket (layer1b) + asset gate" },
  { key: "story", title: "Story Selection", blurb: "per-card analytical stories for the routed page (layer1a/story_builder.py)" },
  { key: "layer2", title: "Layer 2", blurb: "per-card emit: keep/swap + exact_metadata + data_instructions (layer2/emit)" },
  { key: "executor", title: "Executor", blurb: "per-card NEURACT fill via ems_exec (SQL reads, special renderers)" },
  { key: "validation", title: "Validation", blurb: "pre-L2 data validation + fab-guard / honest-blank reasons" },
  { key: "renderer", title: "Renderer", blurb: "served cards: render verdicts, leaf coverage, the response the FE renders" },
];

/** obs/stage.py record name → display stage */
const RAW_TO_STAGE: Record<string, StageKey> = {
  PROMPT: "prompt",
  knowledge: "knowledge",
  "1a": "page", granularity_reconcile: "page", preflight_reroute: "page", reflect: "page", layer1a: "page",
  "1b": "asset", layer1b: "asset", asset_gate: "asset", degrade: "asset",
  "L2.card": "layer2", "L2.swap_revert": "layer2", layer2: "layer2", notes: "layer2",
  exec: "executor",
  validate: "validation", validation: "validation",
  RESPONSE: "renderer", RESPONSE_MULTI: "renderer",
};

/** admin/ai_usage.py stage label → display stage */
const AI_TO_STAGE: Record<string, StageKey> = {
  knowledge: "knowledge",
  "1a.route": "page",
  "1a.stories": "story",
  "1b.asset_resolve": "asset", "1b.columns": "asset",
  l2_emit: "layer2",
  narrative: "executor",           // insight narrator runs INSIDE the executor's special renderer
  llm: "layer2",                   // untagged fallback — label shown verbatim on the row
};

/** obs/failures.py stage value → display stage (reason rows are the per-leaf honest-blank channel → Validation) */
const FAIL_TO_STAGE: Record<string, StageKey> = {
  knowledge: "knowledge",
  layer1a: "page", preflight_reroute: "page", reflect: "page",
  layer1b: "asset",
  llm: "layer2", layer2: "layer2", "L2.card": "layer2", notes: "layer2",
  exec: "executor",
  validate: "validation", validation: "validation", reason: "validation",
  RESPONSE: "renderer",
};

/** failure reasons that are DEFECTS (red); everything else (per-leaf honest-blank vocabulary) is a warning */
const ERROR_REASONS = new Set([
  "stage_error", "card_fail", "exec_fail", "layer-exception", "data_unavailable",
  "timeout", "transport", "no_json", "parse", "truncated", "over_budget", "stories_llm_failed",
]);
export const failureSeverity = (f: FailureRow): "error" | "warning" => {
  const r = (f.reason || "").toLowerCase();
  return ERROR_REASONS.has(r) || r.startsWith("http_") ? "error" : "warning";
};

const ts = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
};

export type StageBundle = {
  key: StageKey; title: string; blurb: string;
  records: TimelineRecord[];
  aiCalls: AiCall[];
  sql: SqlRow[];
  errors: FailureRow[];
  warnings: FailureRow[];
  latency_ms: number | null;       // ≈ wall for this stage within the selected execution (see per-stage rules)
  tokens: { prompt: number; completion: number } | null;
  status: "ok" | "warn" | "error" | "skipped";
};

/** SQL assignment: neuract reads are the executor's fills (or L2-window grounding probes); catalog reads go to the
 *  stage whose time window holds them, nudged by table names. */
function assignSql(row: SqlRow, marks: Marks): StageKey {
  const t = ts(row.ts);
  const text = (row.sql || "").toLowerCase();
  if ((row.db || "").includes("neuract") || /gic_/.test(text)) {
    if (t !== null && marks.gate !== null && marks.l2End !== null && t >= marks.gate && t <= marks.l2End) return "layer2";
    if (t !== null && marks.validate !== null && t <= marks.validate) return "validation";
    return "executor";
  }
  if (/lt_mfm|lt_panels|device_mapping/.test(text)) return "asset";
  if (/page_specs|page_layout|card_titles|routable_pages/.test(text)) return "page";
  if (t === null) return "page";
  if (marks.oneA !== null && t <= marks.oneA + 500) return "page";
  if (marks.oneB !== null && t <= marks.oneB + 500) return "asset";
  if (marks.l2End !== null && t <= marks.l2End) return "layer2";
  return "executor";
}

type Marks = {
  prompt: number | null; oneA: number | null; oneB: number | null; validate: number | null;
  gate: number | null; l2End: number | null; execEnd: number | null; response: number | null;
};

function findTs(records: TimelineRecord[], stage: string, last = false): number | null {
  const hits = records.filter((r) => r.stage === stage);
  if (!hits.length) return null;
  return ts(hits[last ? hits.length - 1 : 0].ts);
}

/** Fold one execution's slice of the trace into the nine display-stage bundles. */
export function buildStages(exec: Execution | null, aiCalls: AiCall[], sql: SqlRow[], failures: FailureRow[]): StageBundle[] {
  const records = exec?.records ?? [];
  const marks: Marks = {
    prompt: findTs(records, "PROMPT"),
    oneA: findTs(records, "1a"),
    oneB: findTs(records, "1b"),
    validate: findTs(records, "validate"),
    gate: findTs(records, "asset_gate"),
    l2End: findTs(records, "layer2", true) ?? findTs(records, "notes", true),
    execEnd: findTs(records, "exec", true),
    response: findTs(records, "RESPONSE", true) ?? findTs(records, "RESPONSE_MULTI", true),
  };

  const bundles = new Map<StageKey, StageBundle>(
    STAGES.map((s) => [s.key, {
      ...s, records: [], aiCalls: [], sql: [], errors: [], warnings: [],
      latency_ms: null, tokens: null, status: "skipped" as const,
    }]),
  );
  const put = <T,>(key: StageKey, list: (b: StageBundle) => T[], item: T) => list(bundles.get(key)!).push(item);

  for (const r of records) put(RAW_TO_STAGE[r.stage] ?? "renderer", (b) => b.records, r);
  for (const c of aiCalls) put(AI_TO_STAGE[c.stage] ?? "layer2", (b) => b.aiCalls, c);
  for (const q of sql) put(assignSql(q, marks), (b) => b.sql, q);
  for (const f of failures) {
    const key = FAIL_TO_STAGE[f.stage || ""] ?? "validation";
    put(key, (b) => (failureSeverity(f) === "error" ? b.errors : b.warnings), f);
  }

  // per-stage ≈latency from the spine marks (1a∥1b both measure from PROMPT; stage records are END markers)
  const span = (a: number | null, b: number | null) => (a !== null && b !== null && b >= a ? Math.round(b - a) : null);
  const lat: Partial<Record<StageKey, number | null>> = {
    page: span(marks.prompt, marks.oneA),
    asset: span(marks.prompt, marks.oneB),
    validation: span(Math.max(marks.oneA ?? 0, marks.oneB ?? 0) || null, marks.validate),
    layer2: span(marks.gate ?? marks.validate, marks.l2End),
    executor: span(marks.l2End, marks.execEnd),
    renderer: span(marks.execEnd ?? marks.l2End, marks.response),
  };
  for (const [k, v] of Object.entries(lat)) bundles.get(k as StageKey)!.latency_ms = v ?? null;

  for (const b of bundles.values()) {
    const p = b.aiCalls.reduce((s, c) => s + (c.ptok || 0), 0);
    const c = b.aiCalls.reduce((s, x) => s + (x.ctok || 0), 0);
    b.tokens = b.aiCalls.length ? { prompt: p, completion: c } : null;
    const recError = b.records.some((r) =>
      r.fields.ERROR !== undefined || r.fields.fail || r.fields.ok === false ||
      (b.key === "validation" && r.fields.verdict === "fail"));
    if (b.errors.length || recError) b.status = "error";
    else if (b.warnings.length || b.records.some((r) => r.fields.gap === true || (r.fields.gaps || 0) > 0)) b.status = "warn";
    else if (b.records.length || b.aiCalls.length || b.sql.length) b.status = "ok";
    else b.status = "skipped";
  }
  return STAGES.map((s) => bundles.get(s.key)!);
}
