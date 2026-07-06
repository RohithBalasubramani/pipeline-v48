// payload → props (story args → component props) for the feeder voltage-current fill cards.
//
// FRAMES ARE RETIRED. The host emits `frames={}`; the ONLY data source is the Layer-2 completed
// payload (real neuract values + honest-blank '—', shape = the CMD V2 story args). So each card
// reads its slice straight off the payload — no ems_backend frame, no live mapper, no reducer.
//
// Payload shapes (the harvested Storybook story args):
//   history card (44/46): { variant, history: { data: HistoryPanelData } }
//   health  card (45):    { variant, health:  { data: HealthCardData, phaseVariant } }
//
// The sanitize* NaN-guards (the panel-overview-real-time-monitoring sanitizeSupply pattern) stay:
// every array HistoryPanel/HealthSummaryPanel `.map`s is guaranteed an array, and every scalar they
// feed a scale/Math/toFixed op is guaranteed finite — so a Layer-2-elided or honest-blanked leaf
// (missing / null / '—') renders the component's OWN blank shape (gap / dropped ref-line / empty
// strip / '—') instead of a crash or an SVG NaN. An all-blank payload → chrome + dashes, never NaN.
import { type PhaseVariant } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { createUnavailableVoltageCurrentViewModel } from "@cmd-v2/pages/electrical/tabs/voltage-current/voltageCurrentViewModel";
import type {
  HealthCardData,
  HistoryPanelData,
  VoltageCurrentViewModel,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

// History story render: <HistoryPanel data={history.data} />
export function historyData(payload: any): HistoryPanelData | undefined {
  return payload?.history?.data;
}
// Health story render: <HealthSummaryPanel data={health.data} phaseVariant={health.phaseVariant} />
export function healthData(payload: any): HealthCardData | undefined {
  return payload?.health?.data;
}
export function healthPhaseVariant(payload: any): PhaseVariant {
  return (payload?.health?.phaseVariant as PhaseVariant) ?? "rows";
}

/* ── CMD V2's OWN honest-blank defaults (ALWAYS-DRAW last resort) ──────────────────────────────
 * When the Layer-2 payload elides a card's whole slice (no data leaf at all), fall back to CMD V2's
 * own structured-empty view-model: series [], metrics/phases/stats "—", chart frames preserved. The
 * panel draws its chrome + honest "—" instead of a blank/null card. NEVER a Storybook seed number. */
function unavailableViewModel(): VoltageCurrentViewModel {
  return createUnavailableVoltageCurrentViewModel({
    source: "api",
    availability: "unavailable",
  } as any);
}
/** Structured-empty `HistoryPanelData` (voltage or current) — draws chrome + "—" when the payload has no series. */
export function unavailableHistory(which: "voltage" | "current"): HistoryPanelData {
  const vm = unavailableViewModel();
  return which === "voltage" ? vm.voltageHistory : vm.currentHistory;
}
/** Structured-empty `HealthCardData` (voltage or current) — draws chrome + "—" when the payload has no metrics/phases. */
export function unavailableHealth(which: "voltage" | "current"): HealthCardData {
  const vm = unavailableViewModel();
  return which === "voltage" ? vm.voltageHealth : vm.currentHealth;
}

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
