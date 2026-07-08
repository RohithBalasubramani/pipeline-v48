// vocab.ts — ONE concern: the LAYOUT VOCABULARY + fallback knobs that steer placement, as DB-tunable rows with a
// code-default mirror. These are the only *policy* string-sets/numbers the placement layer uses; every one of them is a
// cmd_catalog.app_config row (section 'layout_fe', see db/seed_layout_vocab.sql) so it can be retuned WITHOUT a code
// edit. The object below is the code-default MIRROR (identical to the seeded rows) — behaviour is unchanged until a row
// is edited. GENERIC: the placement code keys off THESE tokens, never a hardcoded page name / card id.
//
// DB read path: the server threads the resolved app_config values onto the response as `page.layout.fe_vocab`
// (a shallow object of the same keys); `resolveVocab(layout.fe_vocab)` overlays them on the defaults. Until the server
// populates it (see the wiring note in the audit report), the code-default mirror governs — the banner-band fix, the
// full-span rule and the fallbacks all ship in the mirror, so they are live regardless of the DB read path.

export interface LayoutVocab {
  band_regions: string[];       // page_layout_cards.region values LIFTED into the full-width top band (above the grid)
  rail_regions: string[];       // region values that map to the RAIL (second) column in region-driven (flex) layouts
  flex_primitive: string;       // the layout_primitive that routes to the RTM composite (region columns, not cell grid)
  default_primitive: string;    // layout_primitive when the page declares none
  fallback_cols: string;        // grid_template_columns when the page declares no real CSS track list
  fallback_gap: string;         // layout_gap default
  fallback_padding: string;     // layout_padding default
  rebase_min_row: number;       // a body row-prose >= this counts a lifted band as its first row → rebase down by 1
}

// CODE-DEFAULT MIRROR — must stay byte-identical to db/seed_layout_vocab.sql.
export const LAYOUT_VOCAB: LayoutVocab = {
  band_regions: ["strip", "header", "top", "banner"],   // 'banner' + 'strip'/'header' are all "…above grid" bands
  rail_regions: ["right", "rail"],
  flex_primitive: "flex",
  default_primitive: "grid",
  fallback_cols: "minmax(0,1fr) 300px",
  fallback_gap: "0.75rem",
  fallback_padding: "1rem",
  rebase_min_row: 2,
};

// Overlay DB-provided overrides (page.layout.fe_vocab, arbitrary subset) on the code-default mirror. Missing/wrong-typed
// keys fall through to the default — never throws, never partially-applies a bad value.
export function resolveVocab(overrides?: Partial<LayoutVocab> | null): LayoutVocab {
  if (!overrides || typeof overrides !== "object") return LAYOUT_VOCAB;
  const out = { ...LAYOUT_VOCAB };
  for (const k of Object.keys(LAYOUT_VOCAB) as (keyof LayoutVocab)[]) {
    const v = (overrides as any)[k];
    if (v == null) continue;
    if (Array.isArray(LAYOUT_VOCAB[k]) ? Array.isArray(v) : typeof v === typeof LAYOUT_VOCAB[k]) (out as any)[k] = v;
  }
  return out;
}

// region ∈ band set?  (case-insensitive; the ONE place band-ness is decided.)
export function isBandRegion(region: string | null | undefined, v: LayoutVocab = LAYOUT_VOCAB): boolean {
  const r = (region || "").toLowerCase().trim();
  return !!r && v.band_regions.includes(r);
}
