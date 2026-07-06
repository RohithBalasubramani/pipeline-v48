// guards.ts — GENERIC null-safety guards at the registry seam [family H, 2026-07-06].
//
// WHY: the CMD_V2 components are READ-ONLY and several of their leaf helpers are unguarded (fmt(null).toLocaleString,
// styles[tone].bg, driver.includes, resolvedFilter.allowedResamples, hours.toFixed). A served payload is honest-
// blanked per-leaf (null / '' / '—'), so any residual blank that reaches one of those sites throws and the Boundary
// masks a REAL card as a blank. These guards make the payload component-safe BEFORE it reaches the component —
// per-LEAF, type-aware, zero fabrication (an underivable state stays unasserted: '—' text, info/neutral color-only
// chrome, or omission — never an invented value).
//
// EVERY rule is contract/key-shape driven — NO card ids, NO per-card forks. The serve boundary (host/display_dash.py)
// and the executor derivations (ems_exec/executor/freshness.py / trend_badge.py) fix future serves at the source;
// this seam is the FE net that also covers already-served payloads. `shims.ts` (imported first) additionally teaches
// the dash string the number-format protocol so unguarded `x.toFixed()` sites render the dash.
//
// Rules (each atomic):
//   g1 freshness contract  — {status,label,tone,lastUpdateLabel}: blank state → the StatusBadge-documented honest
//                            blank (tone 'neutral' grey + label '—' + status 'unknown'). No 'Live'/'Offline' asserted.
//   g2 badge/tone contract — a dict with 'tone'+'label': a blank OR UNKNOWN tone becomes color-only chrome with no
//                            asserted word. Every CMD_V2 badge/pill styles through a state-keyed map
//                            (STYLE_MAP[tone].bg/.dot/.pillBg — StatusPill STATUS_PILL_TONES, StatusBadge PALETTE,
//                            KpiStatStrip KPI_STATUS_DOT_PRESETS, AiInsightCard AI_INSIGHT_TONE, ups
//                            adapters.STATUS_PILL_TONE, RAIL_TONE_TO_DS, HealthSummaryPanel STATUS_PILL_BY_TONE /
//                            DELTA_TONE, KpiMiniCard TREND_PRESETS), so a tone string outside the union of those
//                            enum keysets (KNOWN_TONES below — mirrored per-map from the READ-ONLY CMD_V2 sources)
//                            derefs undefined and THROWS (.bg / .dot). Every blank/unknown badge tone → 'info' —
//                            the ONE token valid through BOTH vocabularies: a DS enum natively (StatusPill/KPI-dot/
//                            StatusBadge/AiInsight all carry 'info') AND the UPS DOMAIN map via the shims.ts alias.
//                            NEVER a domain word like 'success': the HealthMetric-row shape ({label,value,tone,
//                            statusLabel}) feeds the DOMAIN map in the UPS cards but the DS map DIRECTLY in
//                            ThermalLifeCard (KPI_STATUS_DOT_PRESETS['success'].dot throws — reproduced live,
//                            card 74). A blank/unknown scalar 'deltaTone' (domain Δ-chip) → 'info' for the same
//                            reason; 'dsTone' is validated against the DS enum alone. A tone that IS one of the
//                            maps' own keys is NEVER touched.
//   g3 digit-chrome keys   — *decimals/*digits (scalar OR a {thd,pfLow,…} dict of digit counts) holding a non-number
//                            → 0 (a formatter DIGITS input must never be NaN: Intl throws RangeError). Presentation
//                            chrome, not a data claim.
//   g4 sibling rehydrate   — a null OBJECT slot whose SAME-LENGTH, ≥4-char-prefix sibling holds a row-shaped dict
//                            (worstVThd beside worstIThd) → same keyset with every scalar '—' (structure is chrome
//                            the component derefs unconditionally; all leaves stay blank).
//   g5 event filter        — a null/absent 'resolvedFilter' beside a 'filterSelection' → CMD_V2's OWN
//                            resolveEventFilter (derivation via the component's own exported rule, not a guess).
//   g6 headline threading  — the card's REAL generated ai_summary.text fills the 'backendHeadline' seam on every
//                            presentation dict that carries a template 'vocab' (the CMD_V2-designed backend-paragraph
//                            override) so the local compose (unguarded against blank stats) never runs. Real text only.
//   g7 no-assert fallback  — 'driverFallbackCode' → '—': an unmatched/unmeasured driver must not assert "OK".
//   g8 sankey contract     — {nodes[],links[]}: links with a non-finite value are OMITTED (unmeasured flow = no flow
//                            drawn); all links unmeasured → nodes cleared (the primitive's own empty state); a
//                            non-finite node 'layer' anywhere → layers dropped for all (d3's own justify realigns).
//   g9 residual null dash  — any remaining null DICT-scalar becomes '—' EXCEPT enum/geometry/lookup keys (suffix
//                            exclusion list) and nulls inside scalar arrays (a null series point is an honest gap the
//                            chart primitives skip — NEVER dashed).
//   g10 heatmap section    — the RTM heatmap section contract ({feeders[], totalKw/totalKvar}): a feeder whose EVERY
//                            metric is unmeasured is OMITTED from the sample (the heatmap cell formatter is
//                            number-only; omission over a crash — an all-blank sample draws an empty section grid).
//   g11 strip controls     — an events/PQ top-strip presentation ({tiles,tileOrder}) missing its 'controls' dict gets
//                            the empty controls shape ({ariaLabels:{}}) — every inner read is optional downstream
//                            (EventStripControls carries its own defaults for undefined options).
//   g12 ED rail vm         — the energy-distribution vm contract ({sankey,legend,…}) gets its missing chrome subtrees
//                            as typed EMPTY shapes (blank section headers, empty source/consumer rosters) — structure
//                            only, no words, no numbers.
//   g13 composite sampling — the CompositeChartCard vm ({leftAxis,rightAxis,…}) missing 'sampling' gets the picker's
//                            neutral selection ({preset:'today', range:null}) — a UI-control default, not data.
//   g14 event-record omission — an entry of an 'events' array carrying a BLANK 'severity' is OMITTED: every CMD_V2
//                            event rail styles records through a severity-keyed map (SEV[severity].chipBorder — only
//                            warn/danger exist), so a blank discriminant cannot render, and asserting one would
//                            fabricate a severity for an event the executor could not derive (idx '—', empty title).
//                            No derivable event = no event drawn (omission over a fabricated label). Entries with a
//                            real severity are never touched.
//   g15 reference-line contract — the CMD_V2 reference/watch-line payload contracts, all of which feed the
//                            ReferenceLine primitive (TONE_PRESETS[tone].pillBg — keys reference|threshold|advisory|
//                            watch ONLY) at a payload-scaled Y (yScale(entry.value)). Two leaf hazards, both
//                            reproduced live (cards 48/49):
//                            • GEOMETRY — a non-finite 'value' cannot be scaled: it reaches SVG as y1/y2=NaN (an
//                              avg/limit line over an empty view). An unmeasured reference is drawn NOWHERE: the
//                              entry is OMITTED from a *lines/thresholds ARRAY (LoadImpactChart watchLines,
//                              PhaseMonitorChart/ScoreHistoryCard thresholds) and a *line/floor DICT SLOT
//                              (DistortionProfileChart maxLine/minLine, CompositeChartCard floor) is DELETED so the
//                              component's own `slice.maxLine && …` conditional skips the primitive.
//                            • STYLE-MAP — an entry 'tone' outside the ReferenceLine enum (the honest-blank '' / '—',
//                              or a badge tone like 'info' that this map does not carry) throws on
//                              TONE_PRESETS[tone].pillBg. The tone key is DELETED so the component's OWN neutral
//                              applies (LoadImpactChart `line.tone ?? 'watch'`; energy-power Charts ref.tone →
//                              undefined → ReferenceLine's default-param 'reference') — the map-derived neutral via
//                              the component's own documented fallback, never an asserted severity. Runs BEFORE g2
//                              (a watch-line is not a badge — 'info' must never be stamped on it) and BEFORE g4/g9
//                              (a deleted slot cannot be rehydrated or dashed into NaN geometry).
//   g16 zero-row plot      — the asset chart-card family (InsulationAgingCard / ThermalTimelineCard /
//                            VoltageRegulationCard / TapActivityCard / ScoreHistoryCard) shares one contract: a vm
//                            with a *points data array + axis-domain dicts ({max,min,ticks}), an optional `loading`
//                            prop (socket re-bucketing → the card's own skeleton), and a ChartSvg body that derefs
//                            point rows UNCONDITIONALLY (lolPoints[lolPoints.length-1].x — reproduced live, card 77:
//                            points:[] throws undefined.x in ANY browser). A plot with ZERO rows and NOTHING measured
//                            anywhere in the vm (no finite numeric leaf) cannot draw and has no per-leaf remainder to
//                            show — thread the component's OWN `loading` seam (root-level prop, forwarded by the
//                            registry unwrap) so its designed skeleton chrome renders (no words, no numbers, no state
//                            asserted) instead of the crash/Boundary mask. A vm with ANY measured leaf is never
//                            touched (per-LEAF rule: real leaves must surface, never hide behind a skeleton).
//                            Components without a `loading` prop ignore the inert extra prop.
import "./shims";
import { resolveEventFilter } from "@cmd-v2/components/charts/primitives/eventFilterRules";

const DASH = "—";

const blank = (v: any) => v == null || v === "";

// g9 exclusions — keys where a null is either handled by the component's own null-guard, is a lookup/enum
// discriminant (a dash corrupts the lookup), or is geometry/chrome where null means "use default". Suffix match,
// case-insensitive.
// pct — the WHOLE *Pct family is GEOMETRY (percent positions consumed arithmetically or in CSS templates:
// FillBar pct/marker.pct → `calc(${w}% + 4px)`, HealthSummaryPanel band.markerPct → `clamp(16px, ${p}%, …)`,
// LoadAnomaliesChart maxThresholdPct/presentValuePct → yScale, phase widthPct/markerPct → `${clampPct(p)}%`).
// Dashing a null here ships NaN into SVG y1 (ReferenceLine at yScale('—') — reproduced live, card 42) or an invalid
// CSS calc/clamp (cards 52/54/57/66). Left null it either hits the component's own null/`<= 0` guard, a `?? 0`
// coercion (empty bar / floor position — the degenerate-domain view), or renders as the empty string in text — never
// NaN geometry, never an asserted number.
// ymax|ymin|maxy|miny — AXIS-DOMAIN keys (LoadImpactChart/DistortionProfileChart slice yMax/yMin, ScoreHistoryCard
// maxY/minY): consumed ONLY arithmetically by the chart's yScale, never rendered as text. Dashing a null domain makes
// the WHOLE scale NaN ('—' − '—') → every zone band / tick / point ships y=NaN (crash class reproduced live, card 51);
// left null it coerces to 0 in the scale and the component's own degenerate-domain fallback (`range || 1`) renders
// the honest empty view. warnc — the *WarnC scalar °C reference family (ThermalTimelineCard hotspotWarnC): consumed
// only by yTemp() geometry feeding an UNCONDITIONAL ReferenceLine (dashed → y1=NaN — card 76); null degrades to the
// degenerate-domain floor with zero NaN.
const NULL_DASH_EXCLUDE =
  /(pct|ratio|opacity|color|width|height|size|count|index|idx|ms|id|key|keys|hint|metric|mode|kind|type|variant|status|state|tone|dir|glyph|icon|payload|focus|resample|preset|decimals|digits|template|columns|filter|range|date|layer|ymax|ymin|maxy|miny|warnc)$/i;
// The *Pct geometry family (see above): a SERVED dash/blank in one of these slots is the same unmeasured state a null
// is — normalize it BACK to null so the component's own guards/coercions apply instead of NaN arithmetic
// (clampPct('—') → width:'NaN%' — reproduced live, card 66 phase widthPct/markerPct served as '—').
const GEOMETRY_PCT_KEY = /pct$/i;
// EXACT-name geometry/arithmetic keys (suffix matching is unsafe here: 'frequency' ends in 'cy', 'operated' in
// 'rated'). x/y/x1/x2/y1/y2/cx/cy are raw SVG coordinates (EngineSvgChart band {y1,y2} — dashed → NaN y, card 61);
// rated/contracted are the point-row window references whose consumers carry their OWN null guard
// (`points[0]?.rated ?? 0`, `!(value > 0)`) that a dash DEFEATS ('—' is not nullish → buildChartDomain → NaN bar
// y/height, card 16). Left null, the component's own guard renders the honest empty/degenerate view.
const NULL_DASH_EXCLUDE_EXACT = /^(x|y|x1|x2|y1|y2|cx|cy|rated|contracted)$/i;

const DIGIT_KEY = /(decimals|digits)$/i;

function isDict(v: any): v is Record<string, any> {
  return v != null && typeof v === "object" && !Array.isArray(v);
}
const finite = (v: any) => typeof v === "number" && Number.isFinite(v);

// ── g1: freshness view-model contract ({status,label,tone,lastUpdateLabel}) — LiveTag→StatusBadge consumer.
// StatusBadge's own documented blank is `<StatusBadge label="—" tone="neutral"/>` (grey, no asserted state).
function fixFreshness(d: Record<string, any>): boolean {
  if (!("lastUpdateLabel" in d) || !("status" in d) || !("tone" in d)) return false;
  if (blank(d.tone)) d.tone = "neutral";
  if (blank(d.status)) d.status = "unknown";
  if (blank(d.label)) d.label = DASH;
  return true;
}

// ── g2 vocab: the UNION of every state-keyed style map a served tone can index in the reachable CMD_V2 tree —
// mirrored per-map from the READ-ONLY sources (a payload tone carrying one of these keys is a REAL state and is
// never touched; anything else derefs undefined in at least one map and throws):
//   • StatusPill.STATUS_PILL_TONES / KpiStatStrip.KPI_STATUS_DOT_PRESETS → normal|alarm|watch|info
//   • StatusBadge.PALETTE / AiInsightCard.AI_INSIGHT_TONE               → fail|critical|warning|success|info|neutral
//   • ups shared/adapters.STATUS_PILL_TONE (domain)                      → success|warning|danger
//   • HealthSummaryPanel.DELTA_TONE                                      → good|bad|neutral
//   • KpiMiniCard.TREND_PRESETS                                          → stable|rising|falling
//   • UpsCapacityCard deltaTone union (string-compare, no map)           → positive|negative|neutral
//   • misc literal unions (string-compare consumers)                     → default
//   • ReferenceLine.TONE_PRESETS (the g15 family — normalized THERE by key deletion, never stamped 'info' here;
//     listed so a REAL ref-line tone passing this rule is never clobbered) → reference|threshold|advisory|watch
const KNOWN_TONES = new Set([
  "normal", "alarm", "watch", "info",
  "fail", "critical", "warning", "success", "neutral",
  "danger",
  "good", "bad",
  "stable", "rising", "falling",
  "positive", "negative", "default",
  "reference", "threshold", "advisory",
]);
const DS_TONES = new Set(["normal", "alarm", "watch", "info"]); // StatusPill/KPI-dot enum — the 'dsTone' seam
const badTone = (t: any) => blank(t) || typeof t !== "string" || !KNOWN_TONES.has(t);

// ── g2: badge/tone dicts + domain Δ-chips (see header). Never overrides a tone that is a real key of ANY reachable
// style map (KNOWN_TONES). A blank OR unknown tone ('' / '—' / garbage — all seen in served payloads) becomes 'info'
// — the ONE token valid through BOTH vocabularies: a DS enum natively AND the UPS DOMAIN map via the shims.ts alias
// — teal informational chrome, the least assertive tone; the label stays blank so no state word is asserted.
// NEVER a domain word ('success'): the SAME HealthMetric-row shape feeds the DS map DIRECTLY in ThermalLifeCard
// (KPI_STATUS_DOT_PRESETS['success'].dot throws — card 74).
function fixBadge(d: Record<string, any>): void {
  if ("tone" in d && "label" in d && badTone(d.tone)) d.tone = "info";
  // RailStatusPill reads `dsTone` FIRST; a blank STRING defeats its `?? RAIL_TONE_TO_DS[tone]` fallback, and a
  // non-DS word ('success'/'—') indexes STATUS_PILL_TONES[dsTone] undefined → .bg throws. DS enum only.
  if ("dsTone" in d && (blank(d.dsTone) || typeof d.dsTone !== "string" || !DS_TONES.has(d.dsTone))) {
    const map: Record<string, string> = { success: "normal", warning: "alarm" };
    d.dsTone = (typeof d.tone === "string" && map[d.tone]) || "info";
  }
  if ("deltaTone" in d && badTone(d.deltaTone)) d.deltaTone = "info";
}

// ── g3: formatter DIGITS inputs (fmt(value, decimals) → toLocaleString({minimumFractionDigits})) must be numbers —
// a '—'/null digit count is NaN → RangeError. 0 digits = chrome, never a data claim. Handles both the scalar form
// (railDecimals) and the dict form (decimals: {thd, pfLow, pfHigh}).
function fixDigitChrome(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (!DIGIT_KEY.test(k)) continue;
    if (v === null || (typeof v === "string" && !finite(Number(v)))) d[k] = 0;
    else if (isDict(v)) {
      for (const [ik, iv] of Object.entries(v)) if (!finite(iv)) (v as any)[ik] = 0;
    }
  }
}

// ── g4: sibling-homogeneous null-object rehydrate — stats.worstVThd:null beside stats.worstIThd:{...} (same length,
// same 'worst' prefix). The STRUCTURE is chrome the component derefs unconditionally (stats.worstVThd.vThd); every
// scalar leaf is '—' (blank), arrays [], nested dicts recursed — no value asserted.
function commonPrefixLen(a: string, b: string): number {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
}
function blankClone(src: any): any {
  if (Array.isArray(src)) return [];
  if (isDict(src)) {
    const out: Record<string, any> = {};
    for (const [k, v] of Object.entries(src)) out[k] = isDict(v) || Array.isArray(v) ? blankClone(v) : DASH;
    return out;
  }
  return DASH;
}
function rehydrateSiblingObjects(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (v !== null) continue;
    for (const [k2, v2] of Object.entries(d)) {
      if (k2 === k || k2.length !== k.length || !isDict(v2) || Object.keys(v2).length < 3) continue;
      if (commonPrefixLen(k, k2) >= 4) {
        d[k] = blankClone(v2);
        break;
      }
    }
  }
}

// ── g5: a null/absent 'resolvedFilter' beside a 'filterSelection' → derived by CMD_V2's OWN exported
// resolveEventFilter (the exact rule the producer uses). Underivable selection → left alone.
function fixResolvedFilter(d: Record<string, any>): void {
  const sel = d.filterSelection;
  if (!isDict(sel) || blank(sel.preset) || d.resolvedFilter != null) return;
  try {
    d.resolvedFilter = resolveEventFilter({
      preset: sel.preset,
      resample: blank(sel.resample) ? "hourly" : sel.resample,
      customDate: sel.customDate ?? "",
      rangeStart: sel.rangeStart ?? "",
      rangeEnd: sel.rangeEnd ?? "",
    } as any);
  } catch {
    /* underivable → leave (Boundary net) */
  }
}

// ── g7: 'OK' as the driver fallback asserts health for an unmatched/unmeasured driver — the no-assert dash instead.
function fixNoAssertFallback(d: Record<string, any>): void {
  if (typeof d.driverFallbackCode === "string" && d.driverFallbackCode !== DASH) d.driverFallbackCode = DASH;
}

// ── g8: sankey contract — drop unmeasured (non-finite) links; if NOTHING is measured, clear nodes too so the
// primitive's own `nodes.length===0` empty state renders. A non-finite 'layer' on ANY node poisons d3's column
// packing (NaN column index → sparse columns → `column.sort` throws) → drop 'layer' from every node and let d3's own
// justify align by link depth (dense, gap-free).
function fixSankey(s: Record<string, any>): void {
  if (!Array.isArray(s.nodes) || !Array.isArray(s.links)) return;
  if (!s.links.length || !s.links.every((l: any) => isDict(l) && "source" in l && "target" in l)) return;
  const kept = s.links.filter((l: any) => finite(l.value));
  if (kept.length !== s.links.length) {
    s.links = kept;
    if (!kept.length) s.nodes = [];
  }
  let relayer = s.nodes.some((n: any) => isDict(n) && "layer" in n && !finite(n.layer));
  if (!relayer && s.links.length) {
    // DEGENERATE layers: a link's endpoints can never share a layer in a real flow (d3 packs columns from these and
    // a same-layer link leaves whole columns empty → `column.sort` throws). Blanked/zeroed layer writes look exactly
    // like this (every node layer 0).
    const layerOf = new Map(s.nodes.filter(isDict).map((n: any) => [n.id, n.layer]));
    relayer = s.links.some((l: any) => {
      const a = layerOf.get(l.source), b = layerOf.get(l.target);
      return finite(a) && finite(b) && a === b;
    });
  }
  if (relayer && s.links.length) {
    // RECOMPUTE layers from the measured link topology (longest-path — the same layering d3's own depth pass uses).
    // Pure structure derived from the payload's own links: no value invented. Isolated nodes sit at layer 0;
    // FlowSankey dense-packs whatever set results, so columns are always gap-free.
    const depth = new Map<string, number>(s.nodes.filter(isDict).map((n: any) => [n.id, 0]));
    for (let i = 0; i <= s.links.length; i++) {
      let changed = false;
      for (const l of s.links) {
        const d = (depth.get(l.source) ?? 0) + 1;
        if (d > (depth.get(l.target) ?? 0)) {
          depth.set(l.target, d);
          changed = true;
        }
      }
      if (!changed) break;
    }
    for (const n of s.nodes) if (isDict(n)) n.layer = depth.get(n.id) ?? 0;
  }
}

// ── g9: residual honest-dash — a null scalar slot in a DICT renders '—' at the leaf instead of crashing an unguarded
// fmt()/String()/toFixed site (see shims.ts). NEVER inside scalar arrays (null series points are honest gaps), never
// on excluded keys, and never inside an AXIS-DOMAIN dict ({max,min,ticks[]} — the tempAxis/faaAxis/lolAxis contract):
// its max/min are yScale inputs only, and a dashed domain turns the WHOLE scale NaN (every tick/band/reference ships
// y=NaN — reproduced live, card 76); left null they coerce to 0 and the component's own degenerate-domain guard
// (`Math.max(1, tMax - tMin)`) renders the honest empty view.
// POINT-ROW dicts — elements of an array under a *points key ({label, ups, hhf, rated, total, …} — the CMD_V2 chart
// data-row contract). Their fields are SERIES/GEOMETRY inputs (fieldOf(p, key) → scaleY), so a null field is an
// honest gap exactly like a null in a scalar series array (g9 header) and must NEVER be dashed: '—' reaching scaleY
// ships y/height=NaN on the bar rects (reproduced live, card 16 — the null 'hhf' feeder). Marked at the parent visit
// (walk reaches parents first), checked by dashResidualNulls.
const POINT_ROWS = new WeakSet<object>();
function markPointRows(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (!Array.isArray(v) || !/points$/i.test(k)) continue;
    for (const e of v) if (isDict(e)) POINT_ROWS.add(e);
  }
}
function dashResidualNulls(d: Record<string, any>): void {
  if (POINT_ROWS.has(d)) return; // every null in a data row is an honest gap the chart primitives skip
  const axisDomain = Array.isArray(d.ticks) && "max" in d && "min" in d;
  for (const [k, v] of Object.entries(d)) {
    if (axisDomain && (k === "max" || k === "min")) continue;
    if (v === null && !NULL_DASH_EXCLUDE.test(k) && !NULL_DASH_EXCLUDE_EXACT.test(k)) d[k] = DASH;
    else if ((v === DASH || v === "") && GEOMETRY_PCT_KEY.test(k)) d[k] = null; // served dash in a geometry slot
  }
}

// ── g10: RTM heatmap section contract — {feeders:[{id,…}], totalKw|totalKvar}. The heatmap cell formatter is
// number-only (`value.toFixed(2)` for pf) so a fully-unmeasured feeder row CANNOT render; omit it (per-leaf honesty:
// an all-blank sample = an empty section grid, never a fabricated number, never a crash). Identity/chrome keys
// (id/label/…) don't count as measurements.
const FEEDER_IDENTITY = /(id|label|shortlabel|name|color|statuses)$/i;
function fixHeatmapSection(d: Record<string, any>): void {
  if (!Array.isArray(d.feeders) || !("totalKw" in d || "totalKvar" in d)) return;
  d.feeders = d.feeders.filter((f: any) => {
    if (!isDict(f)) return true;
    return Object.entries(f).some(
      ([k, v]) => !FEEDER_IDENTITY.test(k) && !(v == null || v === "" || v === DASH),
    );
  });
}

// ── g11: events/PQ top-strip presentation ({tiles,tileOrder}) — PqTopStrip reads pres.controls.* unconditionally;
// the empty controls shape satisfies every read (all inner options are optional → EventStripControls' own defaults).
function fixStripControls(d: Record<string, any>): void {
  if (Array.isArray(d.tiles) && Array.isArray(d.tileOrder) && !isDict(d.controls)) {
    d.controls = { ariaLabels: {} };
  }
}

// ── g12: energy-distribution vm contract ({sankey,legend,…}) — EnergyInputDistributionCard/EnergyFlowDiagramCard
// deref these chrome subtrees unconditionally. Typed EMPTY completion only (blank headers, empty rosters): structure
// is chrome; no word or number is invented. Never clobbers an existing key.
function fixEnergyDistributionVm(d: Record<string, any>): void {
  if (!isDict(d.sankey) || !Array.isArray(d.legend)) return;
  const ensure = (k: string, v: any) => {
    if (d[k] == null) d[k] = v;
  };
  ensure("inputCardTitle", "");
  ensure("allRowLabel", "");
  ensure("flowCardTitle", "");
  ensure("stageUnit", "");
  ensure("aiSummary", "");
  ensure("sourcesSection", { groupLabel: "", columnHeader: "" });
  ensure("consumersSection", { groupLabel: "", columnHeader: "" });
  ensure("supplied", { label: "", unit: "" });
  ensure("consumed", { label: "", unit: "" });
  ensure("sources", []);
  ensure("consumers", []);
}

// ── g13: CompositeChartCard vm ({leftAxis,rightAxis,…}) — the SamplingPicker prop is required
// (`value.preset` read in a useState initializer). {preset:'today', range:null} = the picker's neutral UI-control
// selection (a control default, not a data claim).
function fixCompositeSampling(d: Record<string, any>): void {
  if ("leftAxis" in d && "rightAxis" in d && Array.isArray(d.series) && d.sampling == null) {
    d.sampling = { preset: "today", range: null };
  }
}

// ── g14: event-record contract — an 'events' array entry with a blank 'severity' is an UNDERIVABLE event (the
// executor found no sample: idx '—', blank title/why). CMD_V2 rails deref SEV[severity] (warn/danger only) per record,
// so the honest, non-fabricating handling is OMISSION of that record — an empty rail is the component's own state for
// "no derivable events". Key-shape driven (an array under an *events key whose dict entries carry 'severity').
function fixEventRecords(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (!/events$/i.test(k) || !Array.isArray(v)) continue;
    if (!v.some((e: any) => isDict(e) && "severity" in e)) continue;
    d[k] = v.filter((e: any) => !(isDict(e) && "severity" in e && blank(e.severity)));
  }
}

// ── g15: reference-line contract (see header). Every payload family below feeds CMD_V2's ReferenceLine primitive
// (TONE_PRESETS[tone].pillBg) at yScale(entry.value). Contract population, verified across all served responses:
//   watchLines[]     {tone,color,label,value}                (LoadImpactChart      — payload tone + payload value)
//   thresholds[]     {color,label,labelColor,value}          (PhaseMonitorChart / ScoreHistoryCard — payload value)
//   referenceLines[] {id,name,unit,separator,tone,placement} (energy-power Charts  — payload tone; value from points,
//                                                             component-gated `!(value > 0)`)
//   maxLine/minLine  {label,value}                           (DistortionProfileChart — payload value, conditional
//                                                             `slice.maxLine && …` render)
//   floor            {label,value}                           (CompositeChartCard  — conditional `view.floor ?` render)
// Non-{label,value} lookalikes (sparkline/timeline/bandThresholds/backendHeadline) fail the shape gate untouched.
const REF_LINE_TONES = new Set(["reference", "threshold", "advisory", "watch"]); // ReferenceLine.tsx TONE_PRESETS keys
const REF_LINE_ARRAY_KEY = /(lines|thresholds)$/i;
const REF_LINE_SLOT_KEY = /(max|min|avg|target|watch|ref|reference|threshold|limit|critical|floor)line$|^floor$/i;
const refLineShaped = (e: any) => isDict(e) && "label" in e && "value" in e;
function fixReferenceLines(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (Array.isArray(v) && REF_LINE_ARRAY_KEY.test(k)) {
      // hazard 1 — unmeasured Y: a {label,value} entry whose value is non-finite cannot be scaled (SVG y1=NaN);
      // the unmeasured reference is drawn NOWHERE (entry omitted). Entries without a 'value' slot resolve their Y
      // from the chart's own points behind the component's own finite gate — left alone.
      const kept = v.filter((e: any) => !(refLineShaped(e) && !finite(e.value)));
      if (kept.length !== v.length) d[k] = kept;
      // hazard 2 — tone outside the ReferenceLine enum ('' / '—' / a badge word): TONE_PRESETS[tone].pillBg throws.
      // DELETE the key so the component's OWN neutral fires (`line.tone ?? 'watch'` / default-param 'reference') —
      // the map-derived neutral via the component's own documented fallback; never an asserted severity.
      for (const e of d[k]) {
        if (isDict(e) && "tone" in e && !(typeof e.tone === "string" && REF_LINE_TONES.has(e.tone))) delete e.tone;
      }
    } else if (REF_LINE_SLOT_KEY.test(k)) {
      // dict SLOT ({label,value} under maxLine/minLine/floor…): non-finite value OR a null slot → DELETE the key so
      // the component's own `slice.maxLine && …` conditional skips the primitive (g4 can then never rehydrate it
      // into chrome and g9 can never dash it into NaN geometry — order: g15 runs before both).
      if ((refLineShaped(v) && !finite(v.value)) || v === null) delete d[k];
    }
  }
}

// ── g16: zero-row plot → the component's OWN socket-loading skeleton (see header). Root-level only: `loading` is a
// component PROP (sibling of the vm key), so the rule runs once on the payload root in guardPayload, never in walk.
function hasFiniteLeaf(node: any): boolean {
  if (finite(node)) return true;
  if (Array.isArray(node)) return node.some(hasFiniteLeaf);
  if (isDict(node)) return Object.values(node).some(hasFiniteLeaf);
  return false;
}
const axisDomainShaped = (v: any) => isDict(v) && Array.isArray(v.ticks) && "max" in v && "min" in v;
function fixEmptyPlotLoading(root: Record<string, any>): void {
  if (root.loading != null) return;
  for (const vm of [root, ...Object.values(root)]) {
    if (!isDict(vm)) continue;
    const zeroRow = Object.entries(vm).some(([k, v]) => /points$/i.test(k) && Array.isArray(v) && v.length === 0);
    if (zeroRow && Object.values(vm).some(axisDomainShaped) && !hasFiniteLeaf(vm)) {
      root.loading = true;
      return;
    }
  }
}

function walk(node: any): void {
  if (Array.isArray(node)) {
    for (const el of node) if (el != null && typeof el === "object") walk(el);
    return;
  }
  if (!isDict(node)) return;
  markPointRows(node);
  fixFreshness(node);
  fixReferenceLines(node);
  fixBadge(node);
  fixResolvedFilter(node);
  fixNoAssertFallback(node);
  fixSankey(node);
  fixHeatmapSection(node);
  fixStripControls(node);
  fixEnergyDistributionVm(node);
  fixCompositeSampling(node);
  fixEventRecords(node);
  rehydrateSiblingObjects(node);
  fixDigitChrome(node);
  dashResidualNulls(node);
  for (const v of Object.values(node)) if (v != null && typeof v === "object") walk(v);
}

// ── g6: thread the card's REAL generated summary into the CMD_V2 backend-paragraph seam. Two touch points:
//   • `backendHeadline` on every presentation dict that carries a template 'vocab' (the V&C AiSummaryCard reads
//     pres.backendHeadline; extra keys on other vocab-dicts are inert), and
//   • a top-level 'backendAiSummary' prop (the HPQ PqAiSummaryCard takes it as a prop) — added by unwrap (registry).
export function aiHeadlineOf(payload: any): string | null {
  const t = payload?.ai_summary?.text ?? payload?.widgets?.ai_summary?.text;
  return typeof t === "string" && t.trim() ? t : null;
}
function threadHeadline(node: any, text: string): void {
  if (Array.isArray(node)) {
    for (const el of node) if (el != null && typeof el === "object") threadHeadline(el, text);
    return;
  }
  if (!isDict(node)) return;
  if (isDict(node.vocab) && node.backendHeadline == null) node.backendHeadline = text;
  for (const v of Object.values(node)) if (v != null && typeof v === "object") threadHeadline(v, text);
}

/** Deep-clone + guard a served card payload so it is component-safe (per-leaf honest, zero fabrication). The source
 *  payload is NEVER mutated. Envelope payloads (topology/asset_3d/narrative) must NOT pass through here — the caller
 *  (renderCmd) applies guards only on the component/compose/fill tiers. */
export function guardPayload(payload: any): any {
  if (payload == null || typeof payload !== "object") return payload;
  let clone: any;
  try {
    clone = structuredClone(payload);
  } catch {
    clone = JSON.parse(JSON.stringify(payload));
  }
  const text = aiHeadlineOf(clone);
  if (text) threadHeadline(clone, text);
  if (isDict(clone)) fixEmptyPlotLoading(clone); // g16 — root-level prop seam, before walk (order-independent of g9)
  walk(clone);
  return clone;
}
