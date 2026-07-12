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
//                            exclusion list), nulls inside scalar arrays (a null series point is an honest gap the
//                            chart primitives skip — NEVER dashed), *points data-row dicts (whole-dict skip), and the
//                            GUARD-consumed MEASURE leaves of a *panels roster row (amps/vAvg/… — a dash there defeats
//                            the component's OWN `p.amps != null` filter → NaN radar auto-scale, card 21; left null).
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
import "../shims";
import { isDict } from "./_shared";
import { walk } from "./walk";
import { aiHeadlineOf, threadHeadline } from "./headline";
import { fixEmptyPlotLoading } from "./zero-row";

export { aiHeadlineOf };

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
