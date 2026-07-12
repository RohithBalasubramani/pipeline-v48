// payload → props for the feeder energy-power fill cards.
//
// Page: individual-feeder-meter-shell/energy-power. Four cards, each rendering its REAL CMD V2 component from the
// Layer-2 completed payload (the harvested Storybook story args `{ variant, data: <slice> }`):
//   39 TodaysEnergyCard         ← data: TodaysEnergyData
//   40 PowerEnergyAnalysisChart ← data: PowerEnergyAnalysisData
//   41 InputOutputEnergyCard    ← data: InputOutputEnergyData
//   42 LoadAnomaliesChart       ← data: LoadAnomaliesData
//
// FRAMES ARE RETIRED. The host emits `frames={}`; the ONLY data source is the payload (real neuract values +
// honest-blank '—'/null, shape = the CMD V2 component's props). So each card reads `payload.data` straight — no
// host-served frame, no live mapper, no reducer.
//
// ALWAYS-DRAWS [GOAL]: when the payload elides a card's whole `data` slice (missing / not a usable object) we fall
// back to CMD V2's OWN `createUnavailableEnergyPowerViewModel` slice — the byte-faithful EMPTY-but-valid shape whose
// chart frame still renders (empty series, valid axis, all label/colour META). Never a blank/null card, never a
// fabricated seed. The producer copies every chrome field (labels/colours/units) byte-identical, so a present slice is
// structurally complete; the only honest-blank concern is DATA leaves — for card 41 the five numeric leaves the card
// reads UNGUARDED (`.toLocaleString()`) are forced finite so an honest-blank scalar renders 0, never a crash.
import {
  createEnergyPowerViewModel,
  createUnavailableEnergyPowerViewModel,
} from "@cmd-v2/pages/electrical/tabs/energy-power/energyPowerViewModel";
import type {
  EnergyPowerSnapshot,
  EnergyPowerTabData,
  InputOutputEnergyData,
  LoadAnomaliesData,
  PowerEnergyAnalysisData,
  TodaysEnergyData,
} from "@cmd-v2/pages/electrical/tabs/energy-power/energyPowerTypes";

const isObj = (v: any): v is Record<string, any> => !!v && typeof v === "object" && !Array.isArray(v);
/** Finite number or the fallback — an honest-blank '—'/null/missing scalar never reaches a numeric op. */
const num = (v: any, fallback: number): number => {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : fallback;
};

/** The card's `data` slice off the completed payload (`{ variant, data }`). */
function slice(payload: any): any {
  return payload?.data;
}

/** CMD V2's OWN byte-faithful EMPTY-but-valid view-model (all four slices; empty series, valid axes, full chrome META).
 *  The ALWAYS-DRAW last resort when the payload has no usable slice — the card draws its structure + honest-empty. */
function unavailableViewModel(): EnergyPowerTabData {
  const snapshot = {
    source: "api",
    availability: "unavailable",
    message: undefined,
    periodOptions: ["Today", "This Week", "This Month"],
  } as unknown as EnergyPowerSnapshot;
  return createUnavailableEnergyPowerViewModel(snapshot);
}

/** Card 39 — Today's Energy: the payload slice when present, else CMD V2's own empty-but-valid TodaysEnergy shape. */
export function todaysEnergyData(payload: any): TodaysEnergyData {
  const d = slice(payload);
  return isObj(d) ? (d as TodaysEnergyData) : unavailableViewModel().todaysEnergy;
}

/** Card 40 — Power Energy Analysis: the payload slice when it carries the plottable `demandBars` array, else CMD V2's
 *  own empty-but-valid PowerAnalysis shape (demandBars [], bars [], valid axis) so the chart still draws. */
export function powerAnalysisData(payload: any): PowerEnergyAnalysisData {
  const d = slice(payload);
  return isObj(d) && Array.isArray((d as any).demandBars)
    ? (d as PowerEnergyAnalysisData)
    : unavailableViewModel().powerAnalysis;
}

/** Card 42 — Load Anomalies: the payload slice when it carries the plottable `anomalies` array, else CMD V2's own
 *  empty-but-valid LoadAnomalies shape (empty series, valid axis, all labels/colours) so the chart still draws. */
export function loadAnomaliesData(payload: any): LoadAnomaliesData {
  const d = slice(payload);
  if (!(isObj(d) && Array.isArray((d as any).anomalies))) return unavailableViewModel().loadAnomalies;
  // MIRROR CMD_V2's OWN null-coalescing (energyPowerViewModel.ts loadAnomalies block): the chart's formatPct/toFixed
  // sites are unguarded, and the suite's own view-model — which we bypass by feeding the slice directly — nullsafes
  // these scalars with `?? 0`. Same rule here (the component's documented empty state, not a fabricated value).
  const a = d as any;
  return {
    ...(d as LoadAnomaliesData),
    maxThresholdPct: a.maxThresholdPct ?? 0,
    presentValuePct: a.presentValuePct ?? 0,
    loadFactorPct: a.loadFactorPct ?? 0,
    surgeEvents: a.surgeEvents ?? 0,
    dipEvents: a.dipEvents ?? 0,
    yMin: a.yMin ?? 0,
    yMax: a.yMax ?? 100,
  };
}

/** Card 41 — Input vs Output Energy. InputOutputEnergyCard reads hvInputKw/lvOutputKw/lossKwh/expectedLossKwh/
 *  efficiencyPct PLAINLY and `.toLocaleString()`s them (NO guard) — a null leaf crashes it. So when the payload slice is
 *  present we spread it (keeping every label/unit/colour META byte-identical) but FORCE those five numeric leaves finite
 *  (honest-blank → 0). When the slice is absent we fall to CMD V2's own empty-but-valid inputOutput shape (which is
 *  fully numeric + labelled). ALWAYS returns a fully-numeric, fully-labelled payload — never null, never a seed. */
export function inputOutputData(payload: any): InputOutputEnergyData {
  const d = slice(payload);
  if (!isObj(d)) return zeroInputOutput();
  return {
    ...(d as InputOutputEnergyData),
    hvInputKw: num((d as any).hvInputKw, 0),
    lvOutputKw: num((d as any).lvOutputKw, 0),
    lossKwh: num((d as any).lossKwh, 0),
    expectedLossKwh: num((d as any).expectedLossKwh, 0),
    efficiencyPct: num((d as any).efficiencyPct, 0),
  };
}

/** Fully-numeric, fully-labelled honest-blank Input/Output card built via the REAL view-model's READY branch (so every
 *  label/unit/colour META is folded on) with a ZERO input/output pair. `createUnavailableEnergyPowerViewModel` sets
 *  inputOutput=null (card would crash on null.toLocaleString), so this is the last-resort default when the payload has
 *  no slice at all — a drawable 0-kW card, never a fabricated number. */
function zeroInputOutput(): InputOutputEnergyData {
  const snapshot = {
    source: "api",
    availability: "ready",
    periodOptions: ["Today", "This Week", "This Month"],
    todaysEnergy: {
      period: "Today",
      activeEnergyKwh: null,
      reactiveEnergyKwh: null,
      totalEnergyKwh: null,
      energyTargetKwh: null,
      subsidyLimitKw: null,
      secKwhPerUnit: null,
    },
    powerAnalysis: {
      period: "Today",
      view: "active-reactive",
      times: [],
      activeEnergyKwh: [],
      reactiveEnergyKwh: [],
      demandBars: [],
      hourlyAverage: [],
      ratedKw: null,
      contractedKw: null,
    },
    inputOutput: {
      hvInputKw: 0,
      lvOutputKw: 0,
      deltaPct: 0,
      lossKwh: 0,
      expectedLossKwh: 0,
      efficiencyPct: 0,
      lossPctOfInput: 0,
    },
    loadAnomalies: {
      period: "Today",
      times: [],
      actualLoadPct: [],
      expectedLoadPct: [],
      expectedRangeDeltaPct: null,
      anomalies: [],
      surgeEventsCount: null,
      dipEventsCount: null,
      maxThresholdPct: null,
      presentValuePct: null,
      loadFactorPct: null,
    },
  } as unknown as EnergyPowerSnapshot;
  const io = createEnergyPowerViewModel(snapshot).inputOutput;
  // hvInput/lvOutput are numbers → createEnergyPowerViewModel always populates inputOutput; the `??` is a type-guard.
  return (io ?? {
    hvInputKw: 0, lvOutputKw: 0, deltaPct: 0, lossKwh: 0, expectedLossKwh: 0, efficiencyPct: 0, lossPctOfInput: 0,
    title: "Input vs Output Energy", hvInputLabel: "HV Input", lvOutputLabel: "LV Output",
    powerUnit: "kW", percentUnit: "%", energyUnit: "kWh", deliveredDescriptor: "delivered",
    lostDescriptor: "lost", lossLabel: "Loss", expectedLossLabel: "Expected Loss",
    efficiencyLabel: "Efficiency", deliveredColor: "#000", lossColor: "#000",
    lostValueColor: "#000", descriptorColor: "#000",
  }) as InputOutputEnergyData;
}
