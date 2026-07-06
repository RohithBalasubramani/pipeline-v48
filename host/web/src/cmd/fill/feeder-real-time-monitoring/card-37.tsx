import React from "react";
// Card 37 — Voltage Monitor Panel (page individual-feeder-meter-shell/real-time-monitoring,
// CMD V2 RealTimeMonitoringTab). VoltageMonitorPanel is a PhaseMonitorPanel.
//
// PAYLOAD-DIRECT (ems_backend RETIRED — `frame` is always empty now). The Layer-2
// completed payload IS the render source: { data: PhaseMonitorViewModel, freshness }
// carrying REAL per-phase R-N/Y-N/B-N series or honest-blank '—' per leaf. The old
// liveRailVM(frame) reduce→map→viewModel path is dead and has been DELETED.
//
// HONEST-DEGRADE + ALWAYS-DRAW: payload elided → CMD V2 "unavailable" slice (structured,
// empty series → "—", NEVER mock). NEVER null.
import { VoltageMonitorPanel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/VoltageMonitorPanel";
import { createUnavailableRealTimeMonitoringViewModel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/realTimeMonitoringViewModel";
import type {
  PhaseMonitorViewModel,
  RealTimeFreshnessViewModel,
} from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/types";
import { phaseMonitorDefault, freshnessDefault } from "./payload-unwrap";

function VoltageMonitorCard({ payload }: { payload: any }) {
  const unavailable = createUnavailableRealTimeMonitoringViewModel();

  const data: PhaseMonitorViewModel = phaseMonitorDefault(payload) ?? unavailable.voltageMonitor;
  const freshness: RealTimeFreshnessViewModel = freshnessDefault(payload) ?? unavailable.freshness;

  return <VoltageMonitorPanel data={data} freshness={freshness} />;
}

export const card37 = (p: any): React.ReactNode => <VoltageMonitorCard payload={p} />;
