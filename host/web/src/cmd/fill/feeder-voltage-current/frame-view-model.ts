// frame → view-model helpers (shared by the feeder voltage-current fill cards).
//
// The page's real hook (useVoltageCurrentData) opens THREE sockets and feeds the
// mapper {socket (column-row), voltageHistorySocket, currentHistorySocket}. In the
// host each card carries exactly ONE ems_backend frame (its own endpoint), so we
// build the matching reducer state and stub the rest. The mapper only needs the
// column-row socket's hasSnapshot flag to proceed; the history sockets fill the
// voltageHistory / currentHistory slices. Whatever slice this card needs is then
// read off the single view-model. REUSES the page's reducers/mapper/view-model —
// no transform is re-implemented here.
import { mapVoltageCurrentSocketToSnapshot } from "@cmd-v2/pages/electrical/tabs/voltage-current/voltageCurrentMapper";
import { createVoltageCurrentViewModel } from "@cmd-v2/pages/electrical/tabs/voltage-current/voltageCurrentViewModel";
import {
  createInitialColumnRowState,
  reduceColumnRowFrame,
} from "@cmd-v2/realtime/columnRowReducer";
import {
  createInitialHistoryState,
  reduceHistoryFrame,
} from "@cmd-v2/realtime/historyFrameReducer";
import type {
  HealthCardData,
  HistoryPanelData,
  VoltageCurrentViewModel,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";
import type { Slot } from "./types";

/** A history envelope carries `buckets`; a column-row snapshot carries `queue`. */
export function isHistoryFrame(frame: any): boolean {
  return !!frame && typeof frame === "object" && Array.isArray(frame.buckets);
}

/** Minimal column-row socket marked snapshotted so the mapper passes its early
 *  gates and reaches the history-bucket build (the queue stays empty → no live
 *  health scalars, which is correct for a history-only card). */
function stubColumnRowSocket() {
  const state = { ...createInitialColumnRowState(), hasSnapshot: true };
  return { state, status: "open" as const };
}

/** Build a column-row socket handle from a live `voltage-current/` frame. */
function columnRowSocketFromFrame(frame: any) {
  const state = reduceColumnRowFrame(createInitialColumnRowState(), frame);
  return { state, status: "open" as const };
}

/** Build a history socket handle from a live `voltage-history/` or
 *  `current-history/` frame. */
function historySocketFromFrame(frame: any) {
  const state = reduceHistoryFrame(createInitialHistoryState(), frame);
  return { state, status: "open" as const };
}

/** Run the page's mapper + view-model over the single live frame, placing it in
 *  the socket slot this card's endpoint corresponds to. Returns the full
 *  view-model (all four card slices) or null when the frame is unusable. */
function viewModelFromFrame(frame: any, slot: Slot): VoltageCurrentViewModel | null {
  if (!frame || typeof frame !== "object") return null;
  const socket =
    slot === "voltage-current" ? columnRowSocketFromFrame(frame) : stubColumnRowSocket();
  const voltageHistorySocket = slot === "voltage-history" ? historySocketFromFrame(frame) : null;
  const currentHistorySocket = slot === "current-history" ? historySocketFromFrame(frame) : null;
  const snapshot = mapVoltageCurrentSocketToSnapshot({
    socket: socket as any,
    voltageHistorySocket: voltageHistorySocket as any,
    currentHistorySocket: currentHistorySocket as any,
    config: null,
  });
  if (!snapshot) return null;
  return createVoltageCurrentViewModel(snapshot);
}

/** Resolve a card's live `HistoryPanelData` (or null to keep the payload default).
 *  Detects which history slice from the frame slot so a swapped/mismatched frame
 *  still falls back cleanly. */
export function liveHistory(frame: any, which: "voltage" | "current"): HistoryPanelData | null {
  try {
    if (!isHistoryFrame(frame)) return null;
    const slot: Slot = which === "voltage" ? "voltage-history" : "current-history";
    const vm = viewModelFromFrame(frame, slot);
    if (!vm) return null;
    const data = which === "voltage" ? vm.voltageHistory : vm.currentHistory;
    return data && Array.isArray(data.series) && data.series.length > 0 ? data : null;
  } catch {
    return null;
  }
}

/** Resolve a card's live `HealthCardData` (or null to keep the payload default). */
export function liveHealth(frame: any, which: "voltage" | "current"): HealthCardData | null {
  try {
    if (isHistoryFrame(frame)) return null; // health needs the column-row frame
    const vm = viewModelFromFrame(frame, "voltage-current");
    if (!vm) return null;
    return which === "voltage" ? vm.voltageHealth : vm.currentHealth;
  } catch {
    return null;
  }
}
