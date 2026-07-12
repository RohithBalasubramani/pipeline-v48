// guards/residual-dash.ts — g9 residual honest-dash + the data-row marking it depends on (split F12, 2026-07-12).
// The POINT_ROWS/PANEL_ROWS WeakSets are module state shared between markDataRows (parent visit) and
// dashResidualNulls (child visit) — they move as ONE unit with the exclusion regexes, exactly as in the monolith.
import { isDict, DASH } from "./_shared";

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

// ── g9: residual honest-dash — a null scalar slot in a DICT renders '—' at the leaf instead of crashing an unguarded
// fmt()/String()/toFixed site (see shims.ts). NEVER inside scalar arrays (null series points are honest gaps), never
// on excluded keys, and never inside an AXIS-DOMAIN dict ({max,min,ticks[]} — the tempAxis/faaAxis/lolAxis contract):
// its max/min are yScale inputs only, and a dashed domain turns the WHOLE scale NaN (every tick/band/reference ships
// y=NaN — reproduced live, card 76); left null they coerce to 0 and the component's own degenerate-domain guard
// (`Math.max(1, tMax - tMin)`) renders the honest empty view.
// DATA-ROW dicts — elements of a chart-series/member-roster array whose measure fields feed the component's OWN null
// gate. Marked at the PARENT visit (walk reaches parents first), read by dashResidualNulls. Two families:
//   • POINT rows — elements of an array under a *points key ({label, ups, hhf, rated, total, …} — the CMD_V2 chart
//     data-row contract). EVERY field is a SERIES/GEOMETRY input (fieldOf(p, key) → scaleY), so a null is an honest gap
//     exactly like a null in a scalar series array and the WHOLE dict is skipped: '—' reaching scaleY ships
//     y/height=NaN on the bar rects (reproduced live, card 16 — the null 'hhf' feeder).
//   • PANEL rows — elements of a *panels member-roster array (the lt-pcc panel-overview fan-out). Only the GUARD-
//     consumed NUMERIC MEASURE leaves are protected (PANEL_MEASURE): the radar FILTERS the roster on a null
//     (`period.panels.filter(p => p.amps != null)`) and the table/strip guard every cell (`p.vAvg == null ? '—' : …`,
//     percentCell, worstTileDisplay — all `== null || !isFinite → '—'`). A g9 dash DEFEATS those guards exactly like
//     the `rated`/`contracted` point-row class: '—' is not nullish, so the two dark UPS members SURVIVE the filter and
//     reach the radar math as strings → Math.max(...,'—')=NaN → niceMax(NaN)=1 → the empty "0..1 octagon" (card 21).
//     Left null, the guard drops the spoke / renders '—'. SCOPED to *panels and to those keys ON PURPOSE — the RTM
//     heatmap formats `feeders[].iUnbalance` number-only (`value.toFixed(1)`) and the harmonics feeder-table formats
//     `iThd/vThd/iThdPk` via the UNGUARDED `fmt()` (`value.toLocaleString()`): those live in *feeders / carry other
//     keys, so they stay DASHED (a null there THROWS; a '—' rides through shims.ts) — never broadened to them.
export const POINT_ROWS = new WeakSet<object>();
export const PANEL_ROWS = new WeakSet<object>();
// The lt-pcc panel-roster nullable measures (voltage-current PanelPeriodState) — every reachable consumer null-guards
// them, so a null is the honest gap; NOT the event-count keys (sag/swell/current/neutral — non-null, rendered raw) nor
// any number-only key (iThd/vThd/kw/kvar/pf — see above). Exact match: no accidental prefix/suffix capture.
const PANEL_MEASURE = /^(amps|vavg|vmax|vmin|vdeviation|iunbalance|neutrala)$/i;
export function markDataRows(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (!Array.isArray(v)) continue;
    if (/points$/i.test(k)) {
      for (const e of v) if (isDict(e)) POINT_ROWS.add(e);
    } else if (/panels$/i.test(k)) {
      for (const e of v) if (isDict(e)) PANEL_ROWS.add(e);
    }
  }
}
export function dashResidualNulls(d: Record<string, any>): void {
  if (POINT_ROWS.has(d)) return; // every null in a *points data row is an honest gap the chart primitives skip
  const panelRow = PANEL_ROWS.has(d); // *panels roster row — its guard-consumed measures stay null (PANEL_MEASURE)
  const axisDomain = Array.isArray(d.ticks) && "max" in d && "min" in d;
  for (const [k, v] of Object.entries(d)) {
    if (axisDomain && (k === "max" || k === "min")) continue;
    if (panelRow && PANEL_MEASURE.test(k)) {
      // guard-consumed panel MEASURE: a null is the honest gap the component's OWN filter/guard handles; a served
      // '—'/'' is that same unmeasured state having DEFEATED the guard (radar kept the spoke → NaN) — repair to null.
      if (v === DASH || v === "") d[k] = null;
      continue;
    }
    if (v === null && !NULL_DASH_EXCLUDE.test(k) && !NULL_DASH_EXCLUDE_EXACT.test(k)) d[k] = DASH;
    else if ((v === DASH || v === "") && GEOMETRY_PCT_KEY.test(k)) d[k] = null; // served dash in a geometry slot
  }
}
