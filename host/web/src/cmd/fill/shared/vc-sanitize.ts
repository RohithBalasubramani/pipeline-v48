// cmd/fill/shared/vc-sanitize.ts — the ONE V&C payload sanitizer (frontend F4, 2026-07-12). sanitizeHistory/
// sanitizeHealth guarded the SAME CMD_V2 HistoryPanelData/HealthCardData contract in two folders with DIVERGENT
// behavior: the feeder copy hid the expected band when non-finite and .filter(isObj)'d stats/legend/series/events;
// the DG copy zeroed expectedMin/Max unconditionally (drawing a degenerate 0-band) and did not object-filter — a
// crash-class fix landing in one folder silently did not protect the other. This is the STRICTER feeder
// implementation, now shared; per-folder slice readers (payload paths genuinely differ) and per-folder
// phaseVariant defaults ("rows" vs "bars") stay in their folders. Verified with the client-gate over saved
// feeder + DG responses (byte-identical clean/throw/NaN counts).
import type {
  HealthCardData,
  HistoryPanelData,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

/* ── sanitize (NaN/shape guards applied to the payload slice) ────────────────────────────────── */

const isObj = (v: any): v is Record<string, any> => !!v && typeof v === "object" && !Array.isArray(v);
const arr = (v: any): any[] => (Array.isArray(v) ? v : []);
/** Finite number or the fallback — an honest-blank '—'/null/missing scalar never reaches a numeric op. */
const num = (v: any, fallback: number): number => {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
};

/** Guard a payload HistoryPanelData so HistoryPanel can NEVER crash or emit NaN:
 *  - every mapped array (stats/legend/series[].values/events/yTicks/xLabels/xLabelIndexes) is an array;
 *  - series bucket values are finite-or-null (null = the component's own line-gap shape);
 *  - yTicks are finite numbers (they flow into Math.round/toFixed);
 *  - minY/maxY finite (yScale denominators), band hidden when expectedMin/Max aren't finite;
 *  - maxLine/minLine dropped (the component's guarded null shape) when their value isn't finite. */
export function sanitizeHistory(d: any): HistoryPanelData {
  const base = isObj(d) ? d : {};
  const hasBand = Number.isFinite(base.expectedMin) && Number.isFinite(base.expectedMax);
  const refLine = (l: any) => (isObj(l) && Number.isFinite(l.value) ? l : undefined);
  return {
    ...base,
    title: typeof base.title === "string" ? base.title : "",
    stats: arr(base.stats).filter(isObj),
    legend: arr(base.legend).filter(isObj),
    series: arr(base.series)
      .filter(isObj)
      .map((s) => ({
        ...s,
        values: arr(s.values).map((v: any) => {
          if (v == null) return null; // gap bucket — LinePath breaks the line
          const n = typeof v === "number" ? v : Number(v);
          return Number.isFinite(n) ? n : null; // '—'/garbage → the component's gap shape
        }),
      })),
    events: arr(base.events).filter(isObj),
    yTicks: arr(base.yTicks).map((t: any) => Number(t)).filter((t: number) => Number.isFinite(t)),
    yTickDecimals: Number.isFinite(base.yTickDecimals) ? base.yTickDecimals : undefined,
    xLabels: arr(base.xLabels),
    xLabelIndexes: arr(base.xLabelIndexes).map((v: any, i: number) => num(v, i)),
    minY: num(base.minY, 0),
    maxY: num(base.maxY, 0),
    expectedMin: hasBand ? base.expectedMin : 0,
    expectedMax: hasBand ? base.expectedMax : 0,
    showExpectedRange: hasBand ? base.showExpectedRange ?? true : false,
    maxLine: refLine(base.maxLine),
    minLine: refLine(base.minLine),
    insight: typeof base.insight === "string" ? base.insight : "",
  } as HistoryPanelData;
}

/** Guard a payload HealthCardData so HealthSummaryPanel can NEVER crash or emit NaN:
 *  metrics/phases/band.labels always arrays; phase/band pcts finite (they hit clampPct/CSS %);
 *  non-object status/summary/band drop to the component's guarded null shape. */
export function sanitizeHealth(d: any): HealthCardData {
  const base = isObj(d) ? d : {};
  return {
    ...base,
    title: typeof base.title === "string" ? base.title : "",
    status: isObj(base.status) ? base.status : undefined,
    summary: isObj(base.summary) ? base.summary : undefined,
    band: isObj(base.band)
      ? { ...base.band, markerPct: num(base.band.markerPct, 50), labels: arr(base.band.labels) }
      : undefined,
    metrics: arr(base.metrics).filter(isObj),
    phases: arr(base.phases)
      .filter(isObj)
      .map((p) => ({
        ...p,
        widthPct: num(p.widthPct, 0),
        markerPct: num(p.markerPct, 0),
        deltaTone: p.deltaTone === "good" || p.deltaTone === "bad" ? p.deltaTone : "neutral",
      })),
    insight: typeof base.insight === "string" ? base.insight : "",
  } as HealthCardData;
}
