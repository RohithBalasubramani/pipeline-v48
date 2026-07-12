// payload → ALWAYS-DRAWABLE view-model slices for the transformer thermal-life fill cards.
//
// Page: transformer-asset-dashboard/thermal-life. Four cards, each rendered from its OWN Layer-2 payload (the harvested
// Storybook story args → real neuract values + honest-blank '—'; host-served is RETIRED so `frame` is always empty and
// the payload is the ONLY data source):
//   74 ThermalLifeCard      ← payload.thermalLife    (stress + winding/oil/loss metric strip)
//   75 LifeCapacityCard     ← payload.lifeCapacity   (life-remaining + derating bars)
//   76 ThermalTimelineCard  ← payload.timeline       (today's hotspot/oil/load/efficiency series)
//   77 InsulationAgingCard  ← payload.aging          (daily FAA + cumulative loss-of-life)
//
// The payload slice IS the card's `vm`. The story args are exactly `{ variant, <slice>: <slice>VM }` (see the CMD V2
// storybook), so each fill card reads `payload.<slice>` and passes it straight to the component as `vm={…}`.
//
// HONEST-DEGRADE [GOAL]: this NEVER returns null and NEVER a fabricated/seed number. Load% / loss / efficiency / derating
// are electrical-derivable and fill REAL from the payload; the winding/oil/hotspot temperatures + the insulation-aging
// FAA/LOL series are DOMAIN metrics with NO neuract column today. Degradation is PER-LEAF: a missing series/scalar gets
// the same 0/empty scaffolding the empty view-model uses (single '—' bucket / '—' tile / 0% empty FillBar) while every
// leaf the payload DOES carry stays real. Every scalar the components dereference with `.toFixed`/axis-math is finitized
// so an honest-blank '—' / null never renders as NaN or crashes (`lifeRemainingYears.toFixed(1)`, chart point scalars,
// axis min/max, FillBar pct). The empty view-model is built by running the REAL `buildThermalLifeViewModel` over a typed
// scaffold (a single placeholder bucket per series — the producer indexes `[len-1]`), never a fabricated seed.
import { buildThermalLifeViewModel } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/viewModel";
import type {
  AgingPoint,
  AxisDomain,
  InsulationAgingVM,
  LifeCapacityCardVM,
  ThermalLifeCardVM,
  ThermalLifeFrame,
  ThermalLifeSnapshot,
  ThermalLifeViewModel,
  ThermalTimelineVM,
  TimelinePoint,
} from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/types";

// ── per-leaf guard-rails ──────────────────────────────────────────────────────────────────────────────────────────────
const rec = (v: any): Record<string, any> =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, any>) : {};
const arr = (a: unknown): any[] => (Array.isArray(a) ? a : []);
/** Finite number or `fallback` — an honest-blank '—' / null / NaN that feeds `.toFixed`/axis/FillBar math must never
 *  render as NaN or throw; pin it to a non-crashing structural default. */
const fin = (v: unknown, fallback = 0): number => (Number.isFinite(Number(v)) ? Number(v) : fallback);
/** A chart axis with finite {min,max,ticks} so GridAxis never scales by NaN. */
const domain = (a: any, empty: AxisDomain): AxisDomain => {
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

// ── the honest-empty view-model (tab's OWN chrome, built by the REAL producer over a scaffold) ────────────────────────
let _empty: ThermalLifeViewModel | null = null;
/** A minimal, structurally-valid `ThermalLifeFrame` with EMPTY domain series (one placeholder bucket, all readings 0/
 *  empty). Run through the REAL `buildThermalLifeViewModel` it yields the tab's typed-empty view-model: blank chart
 *  plots (single '—' bucket → flat line), zeroed KPI scaffolding, all labels/units/colours intact — so every card still
 *  DRAWS its structure. An honest empty frame, never a fabricated seed. */
function emptyViewModel(): ThermalLifeViewModel {
  if (_empty) return _empty;
  const snapshot: ThermalLifeSnapshot = {
    windingTempC: 0,
    oilTempC: null,
    hotspotTempC: 0,
    lossKw: 0,
    loadPct: 0,
    efficiencyPct: 0,
    thermalStressPct: 0,
    agingFactor: 1,
    lifeUsedPct: 0,
    lifeRemainingYears: 0,
    ratedKva: 0,
    deratedKva: 0,
    loadKva: 0,
    headroomKva: 0,
  };
  // ONE placeholder bucket in each series so the producer's `[len-1]` reads never index an empty array; 0/empty so the
  // plot is a flat blank line (no data), never a fabricated trend.
  const timeline: TimelinePoint[] = [
    { slot: "—", hotspotC: 0, oilC: null, windingC: 0, loadPct: 0, efficiencyPct: 0 },
  ];
  const aging: AgingPoint[] = [{ label: "—", faa: 1, lolPct: 0, hotspotPeakC: 0 }];
  const vm = buildThermalLifeViewModel({ variant: "lt", snapshot, timeline, aging });
  // The producer derives `lifeCapacity.deratedFillPct` as loadKva/deratedKva → 0/0 = NaN when deratedKva is 0; pin the
  // FillBar pcts finite (honest 0% empty bar) so the empty baseline never emits a NaN width.
  _empty = {
    ...vm,
    lifeCapacity: {
      ...vm.lifeCapacity,
      lifeFillPct: fin(vm.lifeCapacity.lifeFillPct),
      deratedFillPct: fin(vm.lifeCapacity.deratedFillPct),
    },
  };
  return _empty;
}

// ── payload → per-card sanitized VM (real slice when usable, else the honest-empty chrome) ────────────────────────────
/** ThermalLifeCard slice: stress bar + metric strip. Usable when it carries a metrics array; else the empty chrome.
 *  FillBar pcts finitized. */
export function thermalLifeVM(payload: any): ThermalLifeCardVM {
  const empty = emptyViewModel().thermalLife;
  const s = slice(payload, "thermalLife");
  if (!s || typeof s !== "object" || !Array.isArray(rec(s).metrics)) return empty;
  return {
    ...empty,
    ...s,
    status: rec(s.status).label != null ? s.status : empty.status,
    stressPct: fin(s.stressPct),
    stressBorderPct: fin(s.stressBorderPct, empty.stressBorderPct),
    metrics: arr(s.metrics),
    insight: typeof s.insight === "string" ? s.insight : "",
  };
}

/** LifeCapacityCard slice: two FillBar groups. Usable when it carries a numeric-ish life/derated block; else the empty
 *  chrome. EVERY scalar finitized — `lifeRemainingYears.toFixed(1)` throws on null/'—'. */
export function lifeCapacityVM(payload: any): LifeCapacityCardVM {
  const empty = emptyViewModel().lifeCapacity;
  const s = slice(payload, "lifeCapacity");
  if (!s || typeof s !== "object" || (rec(s).lifeFillPct === undefined && rec(s).deratedFillPct === undefined))
    return empty;
  return {
    ...empty,
    ...s,
    status: rec(s.status).label != null ? s.status : empty.status,
    lifeRemainingYears: fin(s.lifeRemainingYears),
    lifeBaseYears: fin(s.lifeBaseYears, empty.lifeBaseYears),
    lifeFillPct: fin(s.lifeFillPct),
    deratedLoadKva: fin(s.deratedLoadKva),
    deratedKva: fin(s.deratedKva),
    deratedFillPct: fin(s.deratedFillPct),
  };
}

/** ThermalTimelineCard slice: hotspot/oil/load/efficiency series. Usable when it carries a NON-empty points array whose
 *  buckets finitize (the component indexes `points[i]` + `.toFixed` on every scalar); else the empty chrome (single '—'
 *  bucket → flat blank line). Axes finitized; oilC kept nullable (oil row drops out when null).
 *
 *  HONEST-BLANK PRESERVE [Lane-C tier-reorder audit 2026-07-06]: the component's crash-prone dereferences are all
 *  `points[i]`-indexed and the legend rail renders `l.value` as a plain STRING, so an EMPTY-points slice can safely keep
 *  the PAYLOAD's OWN honest-blank legend (`value:'—'`) / insight / labels / axis-titles instead of the scaffold's
 *  fabricated `0.0°C`/`0%` legend readings. Only when there's NO usable slice at all do we fall to the full empty
 *  scaffold. This mirrors CMD_V2's own rule: a legend value is display text, not chart math. */
export function timelineVM(payload: any): ThermalTimelineVM {
  const empty = emptyViewModel().timeline;
  const s = slice(payload, "timeline");
  const usable = !!s && typeof s === "object" && (Array.isArray(rec(s).points) || arr(rec(s).legend).length > 0);
  const points = arr(rec(s).points)
    .map((p: any): TimelinePoint | null => {
      const r = rec(p);
      if (r.slot == null) return null;
      const oil = r.oilC;
      return {
        slot: String(r.slot),
        hotspotC: fin(r.hotspotC),
        oilC: oil == null || !Number.isFinite(Number(oil)) ? null : Number(oil),
        windingC: fin(r.windingC),
        loadPct: fin(r.loadPct),
        efficiencyPct: fin(r.efficiencyPct),
      };
    })
    .filter((p): p is TimelinePoint => p !== null);
  if (!usable) return empty;
  return {
    ...empty,
    ...s,
    points, // empty points → the chart draws its blank axes; the payload's honest legend/insight below stay '—'
    tempAxis: domain(s.tempAxis, empty.tempAxis),
    hotspotWarnC: fin(s.hotspotWarnC, empty.hotspotWarnC),
    // KEEP the payload's honest legend (value:'—') when it has one — the scaffold's `0.0°C` legend is a fabrication.
    legend: arr(s.legend).length ? s.legend : empty.legend,
    insight: typeof s.insight === "string" ? s.insight : "",
  };
}

/** InsulationAgingCard slice: daily FAA + cumulative LOL. Usable when it carries a NON-empty points array (the component
 *  indexes `points[len-1]` + `.toFixed`) OR an honest-blank slice with a legend/kpis; else the empty chrome (single '—'
 *  bucket → flat blank line). Axes + KPI block finitized.
 *
 *  HONEST-BLANK PRESERVE [Lane-C tier-reorder audit 2026-07-06]: the KPI strip renders `String(k.lifeUsedPct)` and each
 *  `legend[].value` as plain TEXT, so an honest-blank '—' passes straight through those. Only `k.agingFactor.toFixed(1)`
 *  and `k.deltaLolPct.toFixed(2)` demand a real number (the component crashes on a string), so THOSE two — and those two
 *  only — stay finitized (agingFactor→1 is the "1× normal" AVR/insulation reference constant the tab itself seeds, NOT a
 *  measurement; deltaLolPct→0). Everything else (lifeUsedPct, lifeNote proxy disclosure, legend, insight) keeps the
 *  payload's OWN honest-blank value — the scaffold's fabricated `0%`/`Loss of Life 0%` legend NEVER overwrites a '—'. */
export function agingVM(payload: any): InsulationAgingVM {
  const empty = emptyViewModel().aging;
  const s = slice(payload, "aging");
  const usable = !!s && typeof s === "object" &&
    (Array.isArray(rec(s).points) || arr(rec(s).legend).length > 0 || rec(s).kpis != null);
  const mapped = arr(rec(s).points)
    .map((p: any): AgingPoint | null => {
      const r = rec(p);
      if (r.label == null) return null;
      return { label: String(r.label), faa: fin(r.faa, 1), lolPct: fin(r.lolPct), hotspotPeakC: fin(r.hotspotPeakC) };
    })
    .filter((p): p is AgingPoint => p !== null);
  // STRUCTURAL FLOOR: InsulationAgingCard computes `areaPath` reading lolPoints[last].x / lolPoints[0].x UNCONDITIONALLY
  // (ChartSvg InsulationAgingCard.tsx:74) — an EMPTY series crashes it (undefined.x). When the meter logs no aging data
  // the series is honestly empty; fall back to the empty view-model's single flat baseline point so the chart draws a
  // flat honest line, never crashes. NOT a fabricated measurement (faa=1× normal reference, label '—'). [card 77]
  const points = mapped.length ? mapped : empty.points;
  if (!usable) return empty;
  const k = rec(s.kpis);
  const hasKpis = rec(s.kpis) != null && Object.keys(rec(s.kpis)).length > 0;
  // `lifeUsedPct` is rendered by `String(k.lifeUsedPct)` — a display-only field, so an honest-blank stays honest: a REAL
  // number passes through, but an unmeasured slot (guard leaves *Pct null, or serves '—') renders the DASH, never the
  // scaffold's fabricated 0. (The guard normalizes a served '—' in a *Pct slot BACK to null — see guards g9 exclude — so
  // both null and '—' mean "unmeasured" here.)
  const DASH = "—";
  const dashText = (v: unknown): any => (v == null || v === "" ? DASH : Number.isFinite(Number(v)) ? Number(v) : v);
  return {
    ...empty,
    ...s,
    points,
    kpis: hasKpis
      ? {
          // String()-rendered → honest '—' shows through unchanged (never fabricated to 0).
          lifeUsedPct: dashText(k.lifeUsedPct),
          lifeNote: typeof k.lifeNote === "string" ? k.lifeNote : empty.kpis.lifeNote,
          // .toFixed-dereferenced → MUST be numeric or the component throws (structural, not a measurement): agingFactor
          // pins to the tab's OWN "1× normal" insulation reference constant, deltaLolPct to 0. These two are the only
          // fields the honest-blank must trade for a structural default; every other kpi/legend/insight stays honest.
          agingFactor: fin(k.agingFactor, 1),
          deltaLolPct: fin(k.deltaLolPct),
        }
      : empty.kpis,
    windowDays: fin(s.windowDays, empty.windowDays),
    lolAxis: domain(s.lolAxis, empty.lolAxis),
    faaAxis: domain(s.faaAxis, empty.faaAxis),
    // KEEP the payload's honest legend (value:'—') — the scaffold's `0%`/`Loss of Life 0%` legend is a fabrication.
    legend: arr(s.legend).length ? s.legend : empty.legend,
    insight: typeof s.insight === "string" ? s.insight : "",
  };
}
