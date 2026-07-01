import React from "react";
// Card 43 · Voltage Health Summary (equipment-detail page — a different CMD V2 page, column-row frame).
//
// LIVE PATH — REUSE the page's OWN CMD V2 reducer + mapper + viewModel, fed by the host's single ems_backend
// snapshot frame instead of a live socket:
//   frame (column-row {columns,queue}) → ColumnRowState → mapVoltageCurrentSocketToSnapshot
//   → createVoltageCurrentViewModel → voltageHealth (HealthCardData).
// HONEST-DEGRADE: the live derivation is wrapped in try/catch; a missing/unmappable frame falls straight
// back to the card's seed payload (its byte-identical default data). NEVER throws on a missing frame.

import { HealthSummaryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { createVoltageCurrentViewModel } from "@cmd-v2/pages/electrical/tabs/voltage-current/voltageCurrentViewModel";
import { mapVoltageCurrentSocketToSnapshot } from "@cmd-v2/pages/electrical/tabs/voltage-current/voltageCurrentMapper";

import {
  createInitialColumnRowState,
  reduceColumnRowFrame,
} from "@cmd-v2/realtime/columnRowReducer";

import { asSnapshotFrame } from "./view-model";

function HealthCard({ health, frame }: { health: any; frame?: any }) {
  let data = health.data;
  try {
    if (frame) {
      const state = reduceColumnRowFrame(createInitialColumnRowState(), asSnapshotFrame(frame) as any);
      const snapshot = mapVoltageCurrentSocketToSnapshot({ socket: { state, status: "open" } as any });
      if (snapshot) {
        const vm = createVoltageCurrentViewModel(snapshot);
        if (vm?.voltageHealth) data = vm.voltageHealth;
      }
    }
  } catch { /* keep seed */ }
  // GUARD: HealthSummaryPanel maps data.metrics (MetricStrip) and data.phases (PhaseRows/PhaseBarRows); Layer 2 elides
  // those array leaves from the seed payload, so render a placeholder instead of crashing on `.map` of undefined.
  if (!data || !Array.isArray(data.metrics) || !Array.isArray(data.phases)) return null;
  return (
    <div className="h-full">
      <HealthSummaryPanel data={data} phaseVariant={health.phaseVariant ?? "rows"} />
    </div>
  );
}

export const card43 = (p: any, f?: any): React.ReactNode =>
  p?.health ? <HealthCard health={p.health} frame={f} /> : null;
