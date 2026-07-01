import React from "react";
// FILL module for page: individual-feeder-meter-shell/real-time-monitoring
// Cards: 36 = Power & Energy Panel, 37 = Voltage Monitor Panel, 38 = Current Monitor Panel.
//
// LIVE path (same recipe as the page's own useRealTimeMonitoringData hook):
//   ems_backend column-row frame  →  ColumnRowState (reduceColumnRowFrame)
//   →  SocketHandleLike { state, status:'open' }
//   →  mapRealTimeMonitoringSocketToSnapshot(...)            (REAL page mapper)
//   →  createRealTimeMonitoringViewModel(snapshot)           (REAL page view-model)
//   →  .powerEnergy / .currentMonitor + .freshness
// We NEVER re-implement a transform — every step is the card's own production code.
//
// HONEST-DEGRADE: if frame is missing/unmappable the try/catch falls back to the
// payload's own default `data` + `freshness` (the byte-identical Storybook args).
import { PowerEnergyPanel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/PowerEnergyPanel";
import { VoltageMonitorPanel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/VoltageMonitorPanel";
import { CurrentMonitorPanel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/CurrentMonitorPanel";
import {
  mapRealTimeMonitoringSocketToSnapshot,
  type SocketHandleLike,
} from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/realTimeMonitoringMapper";
import { createRealTimeMonitoringViewModel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/realTimeMonitoringViewModel";
import {
  createInitialColumnRowState,
  reduceColumnRowFrame,
  type ColumnRowState,
} from "@cmd-v2/realtime/columnRowReducer";
import type { AnyBackendFrame } from "@cmd-v2/api/backend/backendTypes";
import type { RealTimeMonitoringViewModel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/types";

/** True when the object already looks like a reduced ColumnRowState (has a queue). */
function isColumnRowState(x: any): x is ColumnRowState {
  return !!x && typeof x === "object" && Array.isArray((x as any).queue);
}

/**
 * Fold the live ems_backend frame into a ColumnRowState. The frame may arrive as:
 *   - an already-reduced ColumnRowState (has `.queue`)           → use as-is
 *   - a single backend frame {type:'snapshot'|'tick'|...}        → reduce one
 *   - an array of frames (snapshot then ticks)                   → reduce in order
 *   - a wrapper { state } / { frames:[...] } / { frame }         → unwrap, then above
 * Returns null when nothing usable is present (→ caller degrades to payload default).
 */
function stateFromFrame(frame: any): ColumnRowState | null {
  if (frame == null) return null;
  if (isColumnRowState(frame)) return frame;
  if (isColumnRowState(frame.state)) return frame.state;

  const raw = frame.frames ?? frame.frame ?? frame;
  const frames: AnyBackendFrame[] = Array.isArray(raw)
    ? (raw as AnyBackendFrame[])
    : raw && typeof raw === "object" && typeof (raw as any).type === "string"
      ? [raw as AnyBackendFrame]
      : [];
  if (frames.length === 0) return null;

  let state = createInitialColumnRowState();
  for (const f of frames) state = reduceColumnRowFrame(state, f);
  return state.hasSnapshot ? state : null;
}

/**
 * Run the card's REAL production pipeline on the live frame. Returns the full
 * RealTimeMonitoringViewModel (carries powerEnergy + currentMonitor + freshness),
 * or null on any failure so the render fn keeps the payload default.
 */
function liveViewModel(frame: any): RealTimeMonitoringViewModel | null {
  const state = stateFromFrame(frame);
  if (!state) return null;
  const socket: SocketHandleLike = { state, status: "open" };
  const snapshot = mapRealTimeMonitoringSocketToSnapshot({ socket });
  if (!snapshot) return null; // pre-snapshot — keep payload default
  return createRealTimeMonitoringViewModel(snapshot);
}

export const CARDS: Record<number, (payload: any, frame?: any) => React.ReactNode> = {
  // Card 36 — Power & Energy Panel. Story args: { data, freshness, variant }.
  // Panel props: <PowerEnergyPanel data freshness />. Live → vm.powerEnergy + vm.freshness.
  36: (p, frame) => {
    let data = p?.data;
    let freshness = p?.freshness;
    try {
      const vm = liveViewModel(frame);
      if (vm) {
        data = vm.powerEnergy;
        freshness = vm.freshness;
      }
    } catch {
      /* unmappable frame — keep payload defaults */
    }
    if (!data || !freshness || !Array.isArray(data.dataSeries) || data.dataSeries.length === 0) return null;   // guard: PowerEnergyChart maps data.dataSeries (elided in fallback seed)
    return <PowerEnergyPanel data={data} freshness={freshness} />;
  },

  // Card 37 — Voltage Monitor Panel. Story args: { data, freshness, variant }.
  // Panel props: <VoltageMonitorPanel data freshness />. Live → vm.voltageMonitor + vm.freshness.
  // (Was MISSING from this fill → fell through to the generic seed render, whose elided metrics crashed on `.map`.)
  37: (p, frame) => {
    let data = p?.data;
    let freshness = p?.freshness;
    try {
      const vm = liveViewModel(frame);
      if (vm) {
        data = vm.voltageMonitor;
        freshness = vm.freshness;
      }
    } catch {
      /* unmappable frame — keep payload defaults */
    }
    if (!data || !freshness || !Array.isArray(data.legendItems) || !Array.isArray(data.metrics) || !Array.isArray(data.series)) return null;   // guard: PhaseMonitorPanel maps legendItems (line 68, first) + metrics; PhaseMonitorChart maps series
    return <VoltageMonitorPanel data={data} freshness={freshness} />;
  },

  // Card 38 — Current Monitor Panel. Story args: { data, freshness, variant }.
  // Panel props: <CurrentMonitorPanel data freshness />. Live → vm.currentMonitor + vm.freshness.
  38: (p, frame) => {
    let data = p?.data;
    let freshness = p?.freshness;
    try {
      const vm = liveViewModel(frame);
      if (vm) {
        data = vm.currentMonitor;
        freshness = vm.freshness;
      }
    } catch {
      /* unmappable frame — keep payload defaults */
    }
    if (!data || !freshness || !Array.isArray(data.legendItems) || !Array.isArray(data.metrics) || !Array.isArray(data.series)) return null;   // guard: PhaseMonitorPanel maps legendItems (line 68, first) + metrics; PhaseMonitorChart maps series
    return <CurrentMonitorPanel data={data} freshness={freshness} />;
  },
};
