// payload → ALWAYS-DRAWABLE view-model slices for the transformer tap-rtcc fill cards.
//
// Page: transformer-asset-dashboard/tap-rtcc. Four cards, each rendered from its OWN Layer-2 payload (the harvested
// Storybook story args → real neuract values + honest-blank '—'; ems_backend is RETIRED so `frame` is always empty and
// the payload is the ONLY data source):
//   78 TapPositionCard        ← payload.tapPosition   (OLTC current/optimal + RTCC mode — DOMAIN, honest-blank)
//   79 VoltageRegulationCard  ← payload.regulation    (regulated bus voltage timeline — ELECTRICAL, real when present)
//   80 RecentTapChangesCard   ← payload.changes       (today's tap-change log — DOMAIN, honest-blank)
//   81 TapActivityCard        ← payload.activity      (hourly tap ops + lifetime wear — DOMAIN, honest-blank)
//
// The payload slice IS the card's `vm`. The story args are exactly `{ variant, <slice>: <slice>CardVM }` (see the CMD V2
// storybook), so each fill card reads `payload.<slice>` and passes it straight to the component as `vm={…}`.
//
// HONEST-DEGRADE [GOAL]: this NEVER returns null and NEVER a fabricated/seed number. When the payload carries a usable
// slice we SANITIZE it (finitize the chart-math scalars an honest-blank '—' would poison, guarantee every array leaf)
// and render it. When the payload has NO usable slice (Layer 2 skipped / a pure honest-blank skeleton with the slice
// elided) we fall to the tab's OWN typed-empty chrome — built by running the REAL `buildTapRtccViewModel` over a typed
// scaffold, then blanking every plotted/measured value (points → [], gauge/KPI/legend → '—'). The AVR setpoint/dead-band
// constants that seed the scaffold are AVR *configuration* (structural chart chrome — the dashed reference + band
// overlay — NOT a measurement), so no fabricated data number ever reaches the screen.
import {
  LIFETIME_OPS,
  REGULATION_PCT,
  SETPOINT_KV,
} from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/config";
import { buildTapRtccViewModel } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/viewModel";
import type {
  ActivityCardVM,
  ChartAxisVM,
  RegulationCardVM,
  TapChangesCardVM,
  TapPositionCardVM,
  TapRtccFrame,
  TapRtccViewModel,
} from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/types";

const DASH = "—";

// ── per-leaf guard-rails ──────────────────────────────────────────────────────────────────────────────────────────────
const rec = (v: any): Record<string, any> =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, any>) : {};
const arr = (a: unknown): any[] => (Array.isArray(a) ? a : []);
/** Finite number or `fallback` — an honest-blank '—' / null / NaN that feeds chart math (gauge value, axis min/max,
 *  plotted scalar) must never render as NaN%/NaN-px; pin it to a non-crashing structural default. */
const fin = (v: unknown, fallback = 0): number => (Number.isFinite(Number(v)) ? Number(v) : fallback);
/** A chart axis with finite {min,max,ticks} so GridAxis never scales by NaN. */
const axis = (a: any, empty: ChartAxisVM): ChartAxisVM => {
  const r = rec(a);
  return {
    min: fin(r.min, empty.min),
    max: fin(r.max, empty.max),
    ticks: arr(r.ticks).map((t) => fin(t)).filter((t) => Number.isFinite(t)),
  };
};

/** Unwrap a card's Layer-2 payload to its own vm slice. The harvested payload is `{ variant, <key>: VM }`; accept the
 *  slice under `key`, a one-level `{data|vm|payload: …}` wrap, or (defensively) a payload that already IS the slice. */
function slice(payload: any, key: string): any {
  const p = rec(payload);
  return p[key] ?? p.vm ?? p.data ?? p.payload ?? p;
}

// ── the honest-empty view-model (tab's OWN chrome, every value blanked) ───────────────────────────────────────────────
/** A ONE-bucket zero scaffold `TapRtccFrame` — the minimal NON-crashing input `buildTapRtccViewModel` needs (it indexes
 *  `regulation[last]` and reduces over `activity`, so both arrays must be non-empty). The AVR setpoint/regulation come
 *  from the tab's OWN config constants (AVR *configuration* / structural chart chrome — the dashed reference + band
 *  overlay — NOT a measurement), so the producer computes every axis/label/colour. The single bucket is discarded
 *  downstream (its plotted series is blanked to []), so no fabricated point ever reaches the screen. */
function emptyScaffoldFrame(): TapRtccFrame {
  return {
    snapshot: {
      currentTap: 0,
      optimalTap: 0,
      mode: "Auto",
      setpointKv: SETPOINT_KV,
      regulationPct: REGULATION_PCT,
      inRangePct: 0,
      todayOps: 0,
      lifetimeOps: LIFETIME_OPS,
      peakOpsPerHour: 0,
      avgOpsPerHour: 0,
    },
    regulation: [{ label: "", voltageKv: SETPOINT_KV, tap: 0, excursion: false }],
    activity: [{ label: "", count: 0, cumTotal: 0 }],
    changes: [],
  };
}

let _empty: TapRtccViewModel | null = null;
/** The tab's OWN chrome with EVERY plotted/measured value blanked — the honest-empty view-model (cached; pure). Built by
 *  running the real `buildTapRtccViewModel` over the scaffold (titles/axes/labels/colours/units are the tab's own), then
 *  stripping the scaffold's numbers: series points → [] (components draw empty axes), gauge/KPI/legend values → '—'. */
function emptyViewModel(): TapRtccViewModel {
  if (_empty) return _empty;
  const vm = buildTapRtccViewModel(emptyScaffoldFrame());

  const tapPosition: TapPositionCardVM = {
    ...vm.tapPosition,
    gauge: { count: vm.tapPosition.gauge.count, value: 0, optimal: null },
    kpis: vm.tapPosition.kpis.map((k) => ({ ...k, value: DASH, valueColor: undefined })),
    insight: "",
  };
  const changes: TapChangesCardVM = { ...vm.changes, rows: [] };
  const regulation: RegulationCardVM = {
    ...vm.regulation,
    points: [], // no live voltage timeline → component draws its empty axes
    kpis: vm.regulation.kpis.map((k) => ({ ...k, value: DASH })),
    legend: vm.regulation.legend.map((l) => ({ ...l, value: DASH })),
    insight: "",
  };
  const activity: ActivityCardVM = {
    ...vm.activity,
    points: [],
    kpis: vm.activity.kpis.map((k) => ({ ...k, value: DASH })),
    legend: vm.activity.legend.map((l) => ({ ...l, value: DASH })),
    insight: "",
  };
  _empty = { tapPosition, changes, regulation, activity };
  return _empty;
}

// ── payload → per-card sanitized VM (real slice when usable, else the honest-empty chrome) ────────────────────────────
/** TapPositionCard slice: gauge {count,value,optimal}, kpis, insight, status. A slice is "usable" when it carries a
 *  gauge object; else the honest-empty tapPosition chrome. Every gauge scalar finitized so a '—'/NaN never breaks the
 *  SegmentedArcGauge geometry. */
export function tapPositionVM(payload: any): TapPositionCardVM {
  const empty = emptyViewModel().tapPosition;
  const s = slice(payload, "tapPosition");
  if (!s || typeof s !== "object" || rec(s).gauge == null) return empty;
  const g = rec(s.gauge);
  return {
    ...empty,
    ...s,
    status: rec(s.status).label != null ? s.status : empty.status,
    gauge: {
      count: fin(g.count, empty.gauge.count),
      value: fin(g.value, 0),
      optimal: g.optimal == null || !Number.isFinite(Number(g.optimal)) ? null : Number(g.optimal),
    },
    kpis: arr(s.kpis).length ? s.kpis : empty.kpis,
    insight: typeof s.insight === "string" ? s.insight : "",
  };
}

/** RecentTapChangesCard slice: columnLabels + rows. A slice is "usable" when it carries columnLabels; else the empty
 *  chrome (rows [] → the DataTable draws its own "No tap changes today" empty state with real headers). */
export function tapChangesVM(payload: any): TapChangesCardVM {
  const empty = emptyViewModel().changes;
  const s = slice(payload, "changes");
  if (!s || typeof s !== "object" || rec(s).columnLabels == null) return empty;
  return {
    ...empty,
    ...s,
    columnLabels: { ...empty.columnLabels, ...rec(s.columnLabels) },
    rows: arr(s.rows),
  };
}

/** VoltageRegulationCard slice: points + axes + band + kpis + legend. A slice is "usable" when it carries a points
 *  array; else the empty chrome. All chart-math scalars finitized; a '—' point value drops the point (empty plot, no
 *  NaN geometry). */
export function regulationVM(payload: any): RegulationCardVM {
  const empty = emptyViewModel().regulation;
  const s = slice(payload, "regulation");
  if (!s || typeof s !== "object" || !Array.isArray(rec(s).points)) return empty;
  const points = arr(s.points)
    .map((p: any) => {
      const r = rec(p);
      if (r.label == null || !Number.isFinite(Number(r.voltageKv))) return null;
      return { label: String(r.label), voltageKv: Number(r.voltageKv), tap: fin(r.tap), excursion: !!r.excursion };
    })
    .filter((p): p is NonNullable<typeof p> => p !== null);
  return {
    ...empty,
    ...s,
    points,
    setpointKv: fin(s.setpointKv, empty.setpointKv),
    bandLowKv: fin(s.bandLowKv, empty.bandLowKv),
    bandHighKv: fin(s.bandHighKv, empty.bandHighKv),
    voltageAxis: axis(s.voltageAxis, empty.voltageAxis),
    tapAxis: axis(s.tapAxis, empty.tapAxis),
    kpis: arr(s.kpis).length ? s.kpis : empty.kpis,
    legend: arr(s.legend).length ? s.legend : empty.legend,
    insight: typeof s.insight === "string" ? s.insight : "",
  };
}

/** TapActivityCard slice: points + axes + kpis + legend. A slice is "usable" when it carries a points array; else the
 *  empty chrome. All chart-math scalars finitized; a '—' bucket drops the point (empty bars, no NaN geometry). */
export function activityVM(payload: any): ActivityCardVM {
  const empty = emptyViewModel().activity;
  const s = slice(payload, "activity");
  if (!s || typeof s !== "object" || !Array.isArray(rec(s).points)) return empty;
  const points = arr(s.points)
    .map((p: any) => {
      const r = rec(p);
      if (r.label == null) return null;
      return { label: String(r.label), count: fin(r.count), cumTotal: fin(r.cumTotal) };
    })
    .filter((p): p is NonNullable<typeof p> => p !== null);
  return {
    ...empty,
    ...s,
    points,
    countAxis: axis(s.countAxis, empty.countAxis),
    cumAxis: axis(s.cumAxis, empty.cumAxis),
    kpis: arr(s.kpis).length ? s.kpis : empty.kpis,
    legend: arr(s.legend).length ? s.legend : empty.legend,
    insight: typeof s.insight === "string" ? s.insight : "",
  };
}
