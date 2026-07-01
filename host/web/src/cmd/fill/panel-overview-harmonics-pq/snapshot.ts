/**
 * SHARED (mapper concern) — panel-overview-harmonics-pq.
 *
 * Turn one raw ems_backend WS frame into the page snapshot via the PAGE's own
 * mapper. The mapper consumes an aggregate-socket-like { state, status }, so we
 * fold the frame through CMD V2's own reducer first (the same reducer the
 * useMfmAggregateSocket hook uses). Returns null on any failure so callers
 * fall back to the payload default.
 */
import { mapPanelHarmonicsPqAggregateToSnapshot } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/panelHarmonicsPqMapper";
import type { PanelHarmonicsPqSnapshot } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/mockSource";
import {
  createInitialAggregateState,
  reduceAggregateFrame,
} from "@cmd-v2/realtime/aggregateFrameReducer";

export function snapshotFromFrame(frame: any): PanelHarmonicsPqSnapshot | null {
  if (!frame) return null;
  const state = reduceAggregateFrame(createInitialAggregateState(), frame as any);
  const sampling =
    (frame?.widgets?.event_timeline?.sampling as string | undefined) ??
    (frame?.widgets?.config?.sampling as string | undefined);
  const snap = mapPanelHarmonicsPqAggregateToSnapshot(
    { state, status: "open" },
    sampling,
  );
  if (!snap || snap.availability !== "ready" || snap.periods.length === 0) return null;
  return snap;
}
