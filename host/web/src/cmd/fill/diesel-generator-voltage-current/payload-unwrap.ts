// payload unwrap (story args → component props) for the diesel-generator voltage-current fill cards.
//
// The DG V&C story args are the shared-electrical slices (the DG viewModel emits the shared
// `VoltageCurrentViewModel`, so its 4 slices are byte-shaped as HealthCardData / HistoryPanelData):
//   VoltageHealth / CurrentHealth story → args { variant, data: HealthCardData }
//   VoltageHistory / CurrentHistory story → args { variant, data: HistoryPanelData }
// The DG story renders the health cards with `phaseVariant="bars"` (11 kV L-L genset labels), NOT
// the single-char "rows" variant the LT-PCC screens use.
import { type PhaseVariant } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import type {
  HealthCardData,
  HistoryPanelData,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

// History story render: <HistoryPanel data={history.data} />
export function historyData(payload: any): HistoryPanelData | undefined {
  return payload?.data;
}
// Health story render: <HealthSummaryPanel data={health.data} phaseVariant="bars" />
export function healthData(payload: any): HealthCardData | undefined {
  return payload?.data;
}
/** DG genset terminal renders multi-char L-L / R-Y-B-N labels → the `bars` variant (the DG story's
 *  hard-coded `phaseVariant="bars"`); honour a payload override if Layer 2 ever emits one. */
export function healthPhaseVariant(payload: any): PhaseVariant {
  return (payload?.phaseVariant as PhaseVariant) ?? "bars";
}

/** GUARD-RAIL (the sanitizeSupply pattern): HealthSummaryPanel `.map`s `band.labels` (band optional) and runs
 *  Math.min/max on `widthPct`/`markerPct` (the `bars` variant). A partially-elided seed (Layer 2 drops leaves)
 *  or an honest-blank '—' in a pct slot must reach the panel as its OWN guarded shape: a band without a labels
 *  array is dropped (the panel skips the row), a non-finite pct clamps to 0 (empty bar / left marker) — never a
 *  `.map` crash, never a NaN%. `metrics`/`phases` arrays are proven by the caller's usable() gate. */
export function sanitizeHealth(d: HealthCardData): HealthCardData {
  const pct = (n: unknown) => (Number.isFinite(Number(n)) ? Number(n) : 0);
  return {
    ...d,
    band: d.band && Array.isArray(d.band.labels) ? { ...d.band, markerPct: pct(d.band.markerPct) } : undefined,
    phases: d.phases.map((p) => ({ ...p, widthPct: pct(p.widthPct), markerPct: pct(p.markerPct) })),
  };
}

/** GUARD-RAIL: HistoryPanel `.map`s legend/stats/yTicks/xLabels/xLabelIndexes/events/series[i].values and scales
 *  minY/maxY/expectedMin/expectedMax/maxLine.value/minLine.value — the caller's usable() gate only proves `series`,
 *  so guarantee every OTHER array leaf ([] when elided; per-LEAF honest degrade — present leaves keep rendering)
 *  and finitize every scaled scalar: an honest-blank '—' bucket value becomes a null GAP (LinePath breaks the
 *  line), a '—' yTick is dropped (Math.round('—') would render a visible "NaN" tick), a non-finite ref-line is
 *  omitted — never a crash, never a NaN on screen. */
export function sanitizeHistory(d: HistoryPanelData): HistoryPanelData {
  const arr = (a: unknown): any[] => (Array.isArray(a) ? a : []);
  const num = (n: unknown) => (Number.isFinite(Number(n)) ? Number(n) : 0);
  const line = (l: any) => (l && Number.isFinite(Number(l.value)) ? { ...l, value: Number(l.value) } : undefined);
  return {
    ...d,
    stats: arr(d.stats),
    legend: arr(d.legend),
    events: arr(d.events),
    series: arr(d.series).map((s: any) => ({
      ...s,
      values: arr(s?.values).map((v: any) => (v == null || !Number.isFinite(Number(v)) ? null : Number(v))),
    })),
    yTicks: arr(d.yTicks).map(Number).filter((t) => Number.isFinite(t)),
    xLabels: arr(d.xLabels),
    xLabelIndexes: arr(d.xLabelIndexes).map((v: any, i: number) => (Number.isFinite(Number(v)) ? Number(v) : i)),
    minY: num(d.minY),
    maxY: num(d.maxY),
    expectedMin: num(d.expectedMin),
    expectedMax: num(d.expectedMax),
    maxLine: line(d.maxLine),
    minLine: line(d.minLine),
  };
}
