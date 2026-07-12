// Mirror of the /api/run response: host/server.py build_response() (dashboard) + the knowledge envelope.

export interface Slot {
  slot_order?: number | null;
  region?: string | null;
  area?: string | null;
  col_span?: number | null;
  row_span?: number | null;
  tab?: string | null;
  combo_id?: string | null;
  combo_role?: string | null;
  cell?: unknown;
}

export interface Size {
  viewport?: string | null;
  width_px?: number | null;
  height_px?: number | null;
  size_source?: string | null;
}

// One per-leaf honest-gap record (the (i) EXPLAINED-BLANKS marker renders from these; additive telemetry, never a
// render gate). Declared here — the response mirror — and re-exported by cmd/registry for its consumers.
export type GapRecord = {
  slot?: string | null; cause?: string | null; metric?: string | null; fn?: string | null; reason?: string | null;
};

// The render-guarantee VERDICT (host/server.py _enrich_card `render`): the Layer-3 decision the FE safe-renderer obeys.
export interface RenderVerdict {
  verdict?: "render" | "partial" | "honest_blank" | null;
  answerability?: "full" | "partial" | "none" | null;
  reason?: string | null;                       // machine/human reason for a blank/partial/frame-empty
  coverage_note?: string | null;                // 'N of M feeders reporting' for aggregates
  date_control?: "enabled" | "disabled" | null; // ER-7: history-less domains disable the date control
  suppress_default_leaves?: string[];           // NO-SEED-LEAK: FE force-blanks these payload paths (cmd/registry forceBlank)
  watermark?: string | null;                    // 'live' — a blanked slot carries null, never a seed number
  gaps?: GapRecord[] | null;                    // per-leaf honest-gap reasons (the (i) marker)
}

export interface FrameStatus {
  endpoint?: string | null;
  ok?: boolean | null;
  why?: string | null;                          // ER-6: empty/mismatched frame reason surfaced to the card
}

// A card (host/server.py _enrich_card). NOTE: the harvested-Storybook metadata the server used to carry — story_id,
// story_name, variant, storybook_url, component, key_roles, subcards — was dead on the wire (no renderer reads it), so it
// is dropped from this contract. The card renders its CMD V2 component directly from `payload`.
export interface Card {
  card_id: number;
  render_card_id?: number;
  endpoint?: string | null;
  is_history?: boolean | null;
  refetch?: unknown;                              // per-card /api/frame date re-fetch bundle (is_history cards only)
  data_instructions?: unknown;                    // carries consumer (endpoint/range/sampling) for date re-fetch
  title: string;
  story: string;
  role: string;
  slot: Slot;
  size: Size;
  payload: unknown;
  validation: { verdict?: string; reasons?: string[] } | null;
  has_payload: boolean;
  payload_error: string | null;
  render?: RenderVerdict | null;                // render-guarantee verdict (Layer 3)
  frame_status?: FrameStatus | null;            // per-endpoint {ok, why} reason channel
  data_note?: string | null;                    // B1: Layer 2's plain-words proxy/substitution disclosure (additive)
  l2_answerability?: "full" | "partial" | "none" | null; // B1: L2's OWN claim (telemetry; render.answerability is the derived truth)
  asset?: { id?: number | null; name?: string | null; class?: string | null } | null; // MULTI-ASSET: the asset this card belongs to (present only on a compare run; FE groups + labels by it)
}

export interface Candidate {
  mfm_id?: number;
  id?: number;
  name?: string;
  class?: string;
  load_group?: string;
  [k: string]: unknown;
}

// Fields shared by EVERY /api/run response — the dashboard grid AND the knowledge answer. The heavy grid context
// (page/asset/validation/cards) is declared here, not only on DashboardResult, because the host reads several of those
// off an un-discriminated PipelineResult in its render path (host App) BEFORE it branches on `kind`; the knowledge
// envelope omits them at runtime — so always gate on `kind === "knowledge"` before trusting answer/refused.
interface PipelineResultBase {
  ok: boolean;
  prompt: string;
  run_id: string;
  trace_id?: string | null;                      // obs trace identity (obs/middleware) — deep-links the AI Decision Inspector
  elapsed_ms?: number;                           // dashboard branch only; the knowledge envelope omits it
  sb_base?: string;                              // dashboard branch only
  // ASSET-RESOLUTION states (served by build_response): 1b could not pin one asset / the named asset has no data /
  // validation blocked the run — the FE opens the resolution picker instead of the grid.
  asset_pending?: boolean | null;
  asset_no_data?: boolean | null;
  validation_blocked?: boolean | null;
  // HONEST OUTAGE terminal (e.g. the neuract tunnel dropped): show the outage notice, never a silent blank grid.
  data_unavailable?: boolean | null;
  degrade?: { kind?: string | null; reason?: string | null } | null;
  notes?: unknown;
  page: {
    page_key: string | null;
    page_title: string | null;
    shell: string | null;
    metric: string | null;
    intent: string | null;
    story: string | null;
    layout: Record<string, unknown>;
    groups: Array<{ group_id: string; card_ids: number[]; coupling: string[] }>;
  };
  asset: {
    asset: { mfm_id?: number; name?: string; class?: string; table?: string } | null;
    how: string | null;
    candidates: Candidate[];
    n_columns: number | null;
  };
  validation: {
    verdict: string | null;
    how: string | null;
    policy: string | null;
    data_summary: unknown;
    payload_summary: unknown;
  };
  cards: Card[];
  multi_asset?: boolean;                         // MULTI-ASSET compare: cards are tagged by `card.asset` → the FE renders a per-asset grouped grid
  assets?: Array<{ mfm_id?: number; name?: string; class?: string; table?: string }>; // the compared assets (order = card groups)
  // page-level frames/frame_status/live_frame RETIRED (F14, 2026-07-12): data rides on each card's payload; the
  // honest fetch-reason is per-card (card.frame_status).
  date_window?: DateWindow | null;
  errors: Record<string, string>;
}

// DASHBOARD envelope (host/server.py build_response): the resolved card grid + page/asset/validation context.
// build_response stamps kind:"dashboard" on the wire (server.py:97), so the discriminant is REQUIRED and the union
// is fully discriminated. [R10 completed 2026-07-12]
export interface DashboardResult extends PipelineResultBase {
  kind: "dashboard";
}

// KNOWLEDGE envelope (host/server.py /api/run knowledge routing): {ok,prompt,run_id,kind,answer,refused} — a conceptual
// electrical/mechanical answer or the domain refusal, NEVER a card grid. (It structurally inherits the grid fields so
// the host's un-discriminated reads type-check; those fields are absent at runtime.)
export interface KnowledgeResult extends PipelineResultBase {
  kind: "knowledge";
  answer?: string | null;
  refused?: boolean | null;
}

// The /api/run result is one OR the other, discriminated on `kind`: `kind === "knowledge"` → KnowledgeResult (answer/
// refused); anything else → DashboardResult (the card grid).
export type PipelineResult = DashboardResult | KnowledgeResult;

export interface DateWindow {
  range?: string | null;                        // today | yesterday | last-7-days | this-month | custom-range
  start?: string | null;                        // ISO/bare date (custom-range)
  end?: string | null;
  sampling?: string | null;                     // hourly | 2hour | shift | day | week
}
export type OnDateChange = (dw: DateWindow) => void;
