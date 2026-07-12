// payload → ALWAYS-DRAWABLE view-model for the DG engine-cooling fill cards.
//
// Page: diesel-generator-asset-dashboard/engine-cooling. Cards 61 (Thermal Timeline) + 62 (Pressure·Speed·Load) render
// CMD V2's REAL <Panel> (EngineHistoryCharts.tsx). `Panel({ vm, chart })` reads the plotted NUMERIC series from
// `vm.points` (the full EngineCoolingViewModel) and the axes/band/kpis/legend/events/insight CHROME from `chart`
// (one ChartVM). The Layer-2 payload for these cards carries ONLY the `chart` slice (real or honest-blank '—'), NOT the
// series points.
//
// FRAMES=PAYLOADS [architecture]: host-served is RETIRED (the host emits frames={} EMPTY) — the ONLY data source is the
// Layer-2 payload, and the old live-frame / mapper / assetPageSocket path is DELETED. DATA REALITY [honest-degrade]:
// every plotted engine metric (coolant / oil / intake / exhaust temperature, oil pressure, engine speed, load%) is
// ENGINE-DOMAIN telemetry with NO neuract column, so Layer-2 carries no series points. We build CMD V2's OWN typed-empty
// view-model (a single all-zero point → valid axes/bands/legend/KPIs, EMPTY series) and OVERLAY the payload's real
// `chart` chrome (title/kpis/legend/insight) onto the matching chart. Every card STILL DRAWS its full structure with an
// honest empty timeline — never a blank/null card, never CMD V2's demo telemetry (getEngineMockFrame), never a seed.
import { buildEngineCoolingViewModel, type EngineCoolingViewModel, type ChartVM } from "@cmd-v2/pages/assets/diesel-generator/tabs/engine-cooling/viewModel";
import type { ChartId, EngineFrame, EngineHistoryPoint, EngineSnapshot } from "@cmd-v2/pages/assets/diesel-generator/tabs/engine-cooling/types";

/** An all-zero, off-state history point — a structurally-valid, HONEST typed-empty reading (no engine telemetry in
 *  neuract). Every series field is present + numeric so the SVG chart + viewModel never crash and never fabricate. */
const ZERO_POINT: EngineHistoryPoint = {
  label: "",
  coolant: 0,
  oilTemp: 0,
  intake: 0,
  exhaust: 0,
  oilPressure: 0,
  speedPct: 0,
  loadPct: 0,
  speedRaw: 0,
  runState: "off",
};

/** An all-zero instantaneous snapshot — the typed-empty counterpart to ZERO_POINT (present for shape completeness). */
const ZERO_SNAPSHOT: EngineSnapshot = {
  loadPct: 0,
  coolantTemp: 0,
  oilTemp: 0,
  oilPressure: 0,
  intakeTemp: 0,
  exhaustTemp: 0,
  batteryVoltage: 0,
  engineSpeed: 0,
  vibration: 0,
};

/** CMD V2's OWN typed-empty EngineFrame. buildEngineCoolingViewModel's KPI builder reads `points[points.length-1]`
 *  and `Math.max(...points.map(...))`, so an EMPTY points array would crash it — we hand it exactly ONE all-zero
 *  point. That yields the component's honest empty state: all KPIs 0, no events, valid axes/bands/legend. */
function emptyEngineFrame(): EngineFrame {
  const points: EngineHistoryPoint[] = [{ ...ZERO_POINT }];
  return {
    snapshot: { ...ZERO_SNAPSHOT },
    points,
    count: points.length,
    ticks: [0],
    labelAt: (i: number) => points[i]?.label ?? "",
  };
}

/** Overlay a Layer-2 `chart` payload (title / kpis / axes / band / legend / events / insight — real or honest-blank)
 *  onto CMD V2's OWN empty ChartVM: prefer the payload's fields where present, keep the empty-vm's structural defaults
 *  otherwise. The plotted VALUES come from `vm.points` (EMPTY), so `series` stays the empty-vm's own descriptors —
 *  matching the empty points for a consistent honest-blank timeline. Every array leaf defaults to the base's own so a
 *  `.map` never hits undefined; a fully-absent payload chart leaves the base untouched (a valid empty chart). */
function mergeChart(base: ChartVM, p: any): ChartVM {
  if (!p || typeof p !== "object") return base;
  const arr = <T,>(a: unknown, fallback: T[]): T[] => (Array.isArray(a) ? (a as T[]) : fallback);
  return {
    ...base,
    title: typeof p.title === "string" ? p.title : base.title,
    kpis: arr(p.kpis, base.kpis),
    axes: arr(p.axes, base.axes),
    band: p.band && typeof p.band === "object" ? p.band : base.band,
    legend: arr(p.legend, base.legend),
    events: arr(p.events, base.events),
    series: base.series,
    insight: typeof p.insight === "string" ? p.insight : base.insight,
  };
}

/** ALWAYS-DRAWABLE view-model for the two timeline cards: CMD V2's OWN typed-empty (all-zero) view-model built by the
 *  REAL builder, with the Layer-2 payload's real `chart` chrome overlaid onto the given chart id. `chartId` selects
 *  which chart the calling card renders (thermal for 61, mech for 62). NEVER null, NEVER a fabricated seed. */
export function engineCoolingViewModel(payload: any, chartId: ChartId): EngineCoolingViewModel {
  const vm = buildEngineCoolingViewModel(emptyEngineFrame());
  const chart = payload && typeof payload === "object" ? payload.chart : undefined;
  vm.charts = { ...vm.charts, [chartId]: mergeChart(vm.charts[chartId], chart) };
  // BLANKED insight on the empty path [no-fabrication]: with NO telemetry the builder's zero-event branch CLAIMS
  // "All temperatures held the expected band…" — an operational statement about data that does not exist. Keep the
  // Layer-2 payload insight when it carried one (real or honest-blank); otherwise drop the builder's fabricated claim
  // so <AiSummary/> renders an empty line. Zeros stay (honest typed-empty readings).
  if (!(chart && typeof chart === "object" && typeof chart.insight === "string")) {
    vm.charts[chartId] = { ...vm.charts[chartId], insight: "" };
  }
  return vm;
}
