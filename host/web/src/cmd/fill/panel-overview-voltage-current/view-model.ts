// Shared aggregate-page view-model helpers for the lt-pcc panel-overview Voltage&Current tab (cards 18-22).
//
// PAYLOAD-DIRECT (host-served RETIRED — the host emits frames={} EMPTY). The ONLY data
// source is each card's Layer-2 completed `payload` (real neuract values + honest-blank '—',
// shaped as the CMD V2 card props). The old LIVE path (aggregate-envelope frame → AggregateState
// → mapPanelVoltageCurrentAggregateToSnapshot → createPanelVoltageCurrentViewModel) is dead code
// now (no frame ever arrives) and was DELETED — with it went the aggregateFrameReducer + mapper
// imports and the asSnapshotFrame / panelVcViewModel / liveViewModel helpers.
//
// What remains is the HONEST-EMPTY always-draw fallback (chrome-only, ZERO fabricated data) plus
// the pure per-card derivation helpers a card runs over whichever period it renders.

import {
  createPanelVoltageCurrentViewModel,
  periodStats,
  buildVcPresentation,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/viewModel";
import type { VcPresentation } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";
import type {
  PanelPeriodState,
  PanelPeriodStats,
  PanelVoltageCurrentViewModel,
  PeriodBucket,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";
import type { EventTimelinePoint } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventTimelineChart";

/** Resolve the selected period bucket the way VoltageCurrentPanelTab does (no interactivity here —
 *  pick the model's default selected label, falling back to the latest useful bucket). */
export function selectPeriod(data: PanelVoltageCurrentViewModel): { period: PeriodBucket; label: string } {
  const periods = data.periods;
  if (!periods.length) return { period: { label: "—", panels: [] }, label: "—" };
  const label =
    data.defaultSelectedLabel ||
    periods[Math.max(0, periods.length - 2)]?.label ||
    periods[periods.length - 1].label;
  const base = periods.find((p: PeriodBucket) => p.label === label) ?? periods[periods.length - 1];
  const period = base.label === label ? base : { ...base, label };
  return { period, label };
}

/** Stats for the selected bucket — prefer the timeline point's per-mode counts (matches the tab). */
export function statsFor(
  data: PanelVoltageCurrentViewModel,
  period: PeriodBucket,
  label: string,
): PanelPeriodStats {
  const fallback = periodStats(period);
  const point = data.timelinePoints.find((pt: EventTimelinePoint) => pt.label === label);
  if (!point) return fallback;
  return {
    sag: point.sag,
    swell: point.swell,
    current: point.current,
    neutral: point.neutral,
    total: point.sag + point.swell + point.current + point.neutral,
    worstVoltage: { ...fallback.worstVoltage, vDeviation: point.vWorst },
    worstCurrent: { ...fallback.worstCurrent, iUnbalance: point.iWorst },
  };
}

/** Default selected panel id for the bucket (model default, else first row). */
export function selectPanelId(data: PanelVoltageCurrentViewModel, period: PeriodBucket): string {
  if (period.panels.some((p: PanelPeriodState) => p.id === data.defaultSelectedPanelId)) return data.defaultSelectedPanelId;
  return data.defaultSelectedPanelId || period.panels[0]?.id || "";
}

// ── HONEST-EMPTY always-draw fallback [ZERO fabrication] ───────────────────────
// The RULE: every card must DRAW — never return null, NEVER fabricate. When the payload
// elides its data-array leaves, we fall back to an HONEST-EMPTY view-model: an EMPTY-periods
// snapshot ('api' source, periods: []) carrying only the page's real presentation CHROME
// (buildVcPresentation — labels/colours, no data). This is the SAME structure the page's
// api-placeholder branch uses (there is no mock builder here). The component .map()s the empty
// periods → an honest empty timeline/strip; hasPanels() stays false so callers know it's blank.
let _fallbackModel: PanelVoltageCurrentViewModel | null = null;
/** The page's HONEST-EMPTY view-model (memoised): real presentation chrome, ZERO
 *  fabricated data (empty periods/panels/points). Used when the payload supplies no
 *  drawable structure — never a mock. */
export function fallbackViewModel(): PanelVoltageCurrentViewModel {
  if (!_fallbackModel) {
    _fallbackModel = createPanelVoltageCurrentViewModel({
      source: "api",
      availability: "ready",
      periods: [],                          // NO fabricated buckets — honest empty
      presentation: buildVcPresentation(),  // real chrome only (labels/colours), not data
    } as any);
  }
  return _fallbackModel;
}

/** A `{ period, points, stats, selectedPanelId }` bundle from a model — the shape
 *  every card 18-22 needs. Pure; never throws. */
export function bundleFrom(data: PanelVoltageCurrentViewModel) {
  const { period, label } = selectPeriod(data);
  const stats = statsFor(data, period, label);
  const selectedPanelId = selectPanelId(data, period);
  const selectedPanel = period.panels.find((p: PanelPeriodState) => p.id === selectedPanelId);
  return { period, label, stats, selectedPanelId, selectedPanel, points: data.timelinePoints, timeOptions: data.periods.map((p: PeriodBucket) => p.label) };
}

/** `data.presentation` sub-slices, from the CMD V2 default builder — the guaranteed
 *  `pres` source when the payload elided a card's presentation leaf. */
export function defaultPresentation(): VcPresentation {
  return buildVcPresentation();
}

/** A period is drawable when it carries at least one panel row. */
export function hasPanels(period: PeriodBucket | undefined | null): boolean {
  return !!period && Array.isArray(period.panels) && period.panels.length > 0;
}
