// Shared aggregate-page view-model helpers for the lt-pcc panel-overview Voltage&Current tab (cards 18-22).
//
// LIVE PATH — we REUSE the page's OWN CMD V2 reducer + mapper + viewModel exactly as the page hook does, but
// fed by the host's single ems_backend snapshot frame instead of a live socket:
//   frame (aggregate envelope {widgets}) → AggregateState → mapPanelVoltageCurrentAggregateToSnapshot
//   → createPanelVoltageCurrentViewModel → derive selectedPeriod/stats/points like VoltageCurrentPanelTab.
// HONEST-DEGRADE: every live derivation is wrapped in try/catch; a missing/unmappable frame returns null so
// the card falls straight back to its seed payload (byte-identical default data). NEVER throws on a missing frame.

import {
  createPanelVoltageCurrentViewModel,
  periodStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/viewModel";
import { mapPanelVoltageCurrentAggregateToSnapshot } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/panelVoltageCurrentMapper";
import type {
  PanelPeriodState,
  PanelPeriodStats,
  PanelVoltageCurrentViewModel,
  PeriodBucket,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";
import type { EventTimelinePoint } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventTimelineChart";

import {
  createInitialAggregateState,
  reduceAggregateFrame,
} from "@cmd-v2/realtime/aggregateFrameReducer";

/** Ensure the host snapshot frame carries `type:'snapshot'` so the CMD V2 reducers accept it
 *  (fetch_frame may emit type=null for a snapshot). */
export function asSnapshotFrame(frame: any): any {
  if (frame && typeof frame === "object" && frame.type == null) return { ...frame, type: "snapshot" };
  return frame;
}

/** Live view-model for cards 18-22 (aggregate page). null when the frame can't be mapped. */
export function panelVcViewModel(frame: any): PanelVoltageCurrentViewModel | null {
  if (!frame) return null;
  try {
    const state = reduceAggregateFrame(createInitialAggregateState(), asSnapshotFrame(frame) as any);
    const snapshot = mapPanelVoltageCurrentAggregateToSnapshot({ state, status: "open" } as any);
    if (!snapshot || !snapshot.periods?.length) return null;
    return createPanelVoltageCurrentViewModel(snapshot);
  } catch {
    return null;
  }
}

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
