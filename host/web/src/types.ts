// Mirror of host/server.py build_response().

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

export interface SubCard {
  story_id: string | null;
  component: { module: string; export: string } | null;
  story_name: string | null;
  storybook_url: string | null;
  payload: unknown;
}

// The render-guarantee VERDICT (host/server.py _enrich_card `render`): the Layer-3 decision the FE safe-renderer obeys.
export interface RenderVerdict {
  verdict?: "render" | "partial" | "honest_blank" | null;
  answerability?: "full" | "partial" | "none" | null;
  reason?: string | null;                       // machine/human reason for a blank/partial/frame-empty
  coverage_note?: string | null;                // 'N of M feeders reporting' for aggregates
  date_control?: "enabled" | "disabled" | null; // ER-7: history-less domains disable the date control
  slots?: Record<string, { value?: unknown; blank_reason?: string | null; fidelity_note?: string | null; source?: unknown }> | null;
  suppress_default_leaves?: string[];           // NO-SEED-LEAK: FE force-blanks these payload paths
  watermark?: string | null;                    // 'live' — a blanked slot carries null, never a seed number
}

export interface FrameStatus {
  endpoint?: string | null;
  ok?: boolean | null;
  why?: string | null;                          // ER-6: empty/mismatched frame reason surfaced to the card
}

export interface Card {
  card_id: number;
  render_card_id?: number;
  endpoint?: string | null;
  is_history?: boolean | null;
  title: string;
  story: string;
  role: string;
  slot: Slot;
  size: Size;
  story_id: string | null;
  story_name: string | null;
  variant: string | null;
  storybook_url: string | null;
  component: { module: string; export: string } | null;
  payload: unknown;
  key_roles: unknown;
  subcards: SubCard[];
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

export interface PipelineResult {
  ok: boolean;
  prompt: string;
  run_id: string;
  elapsed_ms: number;
  sb_base: string;
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
  frames?: Record<string, unknown>;             // {endpoint: ems_backend frame} — FE feeds frames[card.endpoint] to the card's CMD V2 mapper
  frame_status?: Record<string, FrameStatus>;   // {endpoint: {ok, why}} — the reason channel (ER-6)
  live_frame?: unknown;                          // back-compat: the page-endpoint frame
  date_window?: DateWindow | null;
  errors: Record<string, string>;
}

export interface DateWindow {
  range?: string | null;                        // today | yesterday | last-7-days | this-month | custom-range
  start?: string | null;                        // ISO/bare date (custom-range)
  end?: string | null;
  sampling?: string | null;                     // hourly | 2hour | shift | day | week
}
