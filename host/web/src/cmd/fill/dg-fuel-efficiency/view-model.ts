// payload → ALWAYS-DRAWABLE props for the DG fuel-efficiency fill cards.
//
// Page: diesel-generator-asset-dashboard/fuel-efficiency. Three cards:
//   63 FuelTankAnatomy   ← payload {snapshot, display}  (3D day-tank fill — payload IS the props)
//   64 RunsList          ← payload {stats}              (All Runs / Fuel Log — runs honest-empty)
//   65 FuelCompositeCard ← payload {chart}              (Fuel & Tank timeline — needs a full vm)
//
// FRAMES=PAYLOADS [architecture]: host-served is RETIRED — the host emits `frames={}` EMPTY. The ONLY data source is
// the Layer-2 `payload` (ems_exec-completed: real neuract values + honest-blank '—', already shaped as the CMD V2
// component's props, harvested from Storybook). So every helper here reads the PAYLOAD; there is NO live-frame /
// mapper / assetPageSocket path (that dead host-served branch has been DELETED).
//
// DOMAIN-DATA REALITY [honest-degrade]: fuel level / rate / temp, the fuel-history series, and the run log are DG
// domain telemetry the neuract logging DB does NOT carry. So Layer-2 elides those leaves (null → '—'); we render the
// component's OWN empty/blank state — a 0%-tank snapshot (63), "No runs in this period" (64), an empty timeline (65) —
// never a blank/null card, never a fabricated seed number (the 60% / 107 L·hr mock is FORBIDDEN).
import { buildFuelEfficiencyViewModel } from "@cmd-v2/pages/assets/diesel-generator/tabs/fuel-efficiency/viewModel";
import type {
  ChartVM,
  FuelEfficiencyViewModel,
  FuelFrame,
  FuelSnapshot,
  RunsStats,
} from "@cmd-v2/pages/assets/diesel-generator/tabs/fuel-efficiency/types";
import type { FuelSnapshot as TankSnapshot } from "@cmd-v2/pages/electrical/lt-pcc/tabs/dg-overview/fuelTankDisplay";

/** Finite-or-0 guard: an honest-blank '—' / null / non-numeric slot becomes 0 (the component's guarded blank), so
 *  `.toFixed()` / `Math.min` / the 3D fill never render NaN. Never fabricates a value — 0 is the empty reading. */
const num = (v: unknown): number => (Number.isFinite(Number(v)) ? Number(v) : 0);

/** The typed-EMPTY FuelFrame the tab's OWN builder degrades to: all-zero snapshot, NO history points, NO runs, a
 *  single collapsed tick. `buildFuelEfficiencyViewModel` reads `count`/`ticks`/`labelAt`/`runs`/`snapshot` on the
 *  empty-`last` branch — all present here — so it yields a fully-structured, fully-labelled EMPTY view-model without
 *  crashing. This is CMD V2's own honest empty shape, NOT a fabricated value. */
function emptyFuelFrame(): FuelFrame {
  const snapshot: FuelSnapshot = {
    loadPct: 0,
    fuelLevel: 0,
    fuelRate: 0,
    fuelTemp: 0,
    autonomy: 0,
    sfc: 0,
    efficiency: 0,
    costPerKwh: 0,
  };
  return { snapshot, points: [], runs: [], count: 0, ticks: [0], labelAt: () => "" };
}

/** CMD V2's OWN empty FuelEfficiencyViewModel — structure + labels + a "No fuel data in this window." insight, empty
 *  chart series, zero-valued runs stats, and a 0%-tank snapshot. The base every card fills its real Layer-2 slice over. */
function emptyVm(): FuelEfficiencyViewModel {
  return buildFuelEfficiencyViewModel(emptyFuelFrame());
}

/** Card 65 — the whole `FuelEfficiencyViewModel` for FuelCompositeCard. The Layer-2 payload carries ONLY the `chart`
 *  slice (title / kpis / axes / band / legend / events / insight — real or honest-blank '—'); the numeric time-series
 *  (`vm.points`) is DG fuel telemetry neuract does NOT carry, so it stays the empty vm's EMPTY points (an honest empty
 *  timeline, never a fabricated point). We overlay the payload chart onto the empty vm so the card draws its real
 *  Layer-2 chrome (title/KPIs/legend/insight) over the empty series. NEVER null. */
export function fuelCompositeVm(payload: any): FuelEfficiencyViewModel {
  const vm = emptyVm();
  const chart = payload && typeof payload === "object" ? payload.chart : undefined;
  if (chart && typeof chart === "object") {
    vm.chart = mergeChart(vm.chart, chart);
  }
  return vm;
}

/** Overlay a Layer-2 `chart` payload onto the empty-vm's ChartVM: prefer the payload's fields (real or '—') where
 *  present, keep the empty-vm's structural defaults otherwise. Arrays default to the base's own (so a `.map` never hits
 *  undefined); the series overlay is metadata only — the plotted VALUES come from `vm.points`, which stays empty. */
function mergeChart(base: ChartVM, p: any): ChartVM {
  const arr = <T,>(a: unknown, fallback: T[]): T[] => (Array.isArray(a) ? (a as T[]) : fallback);
  return {
    ...base,
    title: typeof p.title === "string" ? p.title : base.title,
    kpis: arr(p.kpis, base.kpis),
    axes: arr(p.axes, base.axes),
    band: p.band && typeof p.band === "object" ? p.band : base.band,
    legend: arr(p.legend, base.legend),
    events: arr(p.events, base.events),
    // The empty vm has [] points, so overlaying the series descriptors would draw legend/threshold rows for lines with
    // no data. Keep the empty vm's own series (matching its empty points) so the timeline is a consistent honest blank.
    series: base.series,
    insight: typeof p.insight === "string" ? p.insight : base.insight,
  };
}

/** Card 64 — `RunsStats` for RunsList. The Layer-2 payload carries the `stats` slice (title + column labels +
 *  aggregates — real or honest-blank); a missing slice falls to the empty vm's zero-valued, fully-labelled stats so
 *  the header always draws. The run ROWS have no neuract source → always []; RunsList renders its own empty state. */
export function runsStats(payload: any): RunsStats {
  const s = payload && typeof payload === "object" ? payload.stats : undefined;
  return s && typeof s === "object" ? (s as RunsStats) : emptyVm().runsStats;
}

/** The 5-field subset FuelTankAnatomy consumes, pulled off the Layer-2 payload's `snapshot` (real or honest-blank).
 *  EVERY field is finitized (an honest-blank '—' → 0) so the card's `snapshot.fuelLevel.toFixed(0)` and 3D fill draw
 *  an empty (0%) tank, never NaN and never the seed 60% mock. A missing snapshot falls to the empty vm's 0 snapshot. */
export function tankSnapshot(payload: any): TankSnapshot {
  const s = (payload && typeof payload === "object" ? payload.snapshot : undefined) ?? emptyVm().snapshot;
  return {
    fuelLevel: num(s.fuelLevel),
    fuelRate: num(s.fuelRate),
    fuelTemp: num(s.fuelTemp),
    autonomy: num(s.autonomy),
    efficiency: num(s.efficiency),
  };
}

/** Card 63 — the FuelTankDisplay prose the card renders as its title/subtitle/channel detail/AI text. Passed through
 *  from the Layer-2 payload's `display` (real or honest-blank); undefined lets FuelTankAnatomy fall back to its OWN
 *  byte-identical `resolveFuelTankDisplay` defaults (so the card always has a title, never a blank header). */
export function tankDisplay(payload: any): any {
  return payload && typeof payload === "object" ? payload.display : undefined;
}
