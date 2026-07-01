/* ── Frame → CMD V2 state adapters ───────────────────────────────────────
 * Run the ems_backend frames through CMD V2's OWN reducers/mappers/builders so every card fills from the LIVE feed
 * via the page's OWN mappers. Honest-degrade: each returns null when there's no usable frame (the caller keeps the
 * card's payload default — never throws). */
import { mapPowerQualityAggregateToSnapshot } from "@cmd-v2/pages/electrical/tabs/power-quality/powerQualityMapper";
import { mapPowerQualityHistoryToTelemetry } from "@cmd-v2/pages/electrical/tabs/power-quality/powerQualityHistoryMapper";
import { createPowerQualityViewModel } from "@cmd-v2/pages/electrical/tabs/power-quality/viewModel";
import {
  createInitialAggregateState,
  reduceAggregateFrame,
} from "@cmd-v2/realtime/aggregateFrameReducer";
import {
  createInitialHistoryState,
  reduceHistoryFrame,
} from "@cmd-v2/realtime/historyFrameReducer";
import type {
  PowerQualityData,
  PowerQualitySnapshot,
} from "@cmd-v2/pages/electrical/tabs/power-quality/types";
import { isAggregateFrame, isHistoryFrame } from "./guards";

/** Live snapshot for the summary card. Runs the ems_backend aggregate frame through CMD V2's OWN aggregate reducer +
 *  per-feeder mapper. Returns null when there's no usable summary frame (caller keeps the payload default). */
export function liveSnapshot(frame: any): PowerQualitySnapshot | null {
  if (!isAggregateFrame(frame)) return null;
  const state = reduceAggregateFrame(createInitialAggregateState(), frame as any);
  if (!state.hasSnapshot) return null;
  return mapPowerQualityAggregateToSnapshot({
    // PowerQualitySocketLike: the mapper only reads `.state` (+ `.status`/`.closeInfo` on the fatal path).
    socket: { state, status: "open" },
  });
}

/** Live view-model (distortionProfile + loadImpact slices) for the two rail charts. Runs the ems_backend history frame
 *  through CMD V2's OWN history reducer → telemetry mapper → view-model builder. `baseSnapshot` supplies the per-row
 *  limit lines the slice builders read. Returns null when there's no usable history frame. */
export function liveViewModel(frame: any, baseSnapshot: PowerQualitySnapshot): PowerQualityData | null {
  if (!isHistoryFrame(frame)) return null;
  const state = reduceHistoryFrame(createInitialHistoryState(), frame as any);
  const telemetry = mapPowerQualityHistoryToTelemetry({ state });
  if (!telemetry) return null;
  return createPowerQualityViewModel(baseSnapshot, telemetry);
}
