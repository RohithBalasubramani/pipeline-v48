import React from "react";
// Card 38 — Current Monitor Panel (page individual-feeder-meter-shell/real-time-monitoring,
// CMD V2 RealTimeMonitoringTab). CurrentMonitorPanel is a PhaseMonitorPanel (same shape as 37).
//
// PAYLOAD-DIRECT (ems_backend RETIRED — `frame` is always empty now). The Layer-2
// completed payload IS the render source: { data: PhaseMonitorViewModel, freshness }
// carrying REAL per-phase R/Y/B current series or honest-blank '—' per leaf. The old
// liveRailVM(frame) reduce→map→viewModel path is dead and has been DELETED.
//
// HONEST-DEGRADE + ALWAYS-DRAW: payload elided → CMD V2 "unavailable" slice (structured,
// empty series → "—", NEVER mock). NEVER null.
import { CurrentMonitorPanel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/CurrentMonitorPanel";
import { createUnavailableRealTimeMonitoringViewModel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/realTimeMonitoringViewModel";
import type {
  PhaseMonitorViewModel,
  RealTimeFreshnessViewModel,
} from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/types";
import { phaseMonitorDefault, freshnessDefault } from "./payload-unwrap";

function CurrentMonitorCard({ payload }: { payload: any }) {
  const unavailable = createUnavailableRealTimeMonitoringViewModel();

  const data: PhaseMonitorViewModel = phaseMonitorDefault(payload) ?? unavailable.currentMonitor;
  const freshness: RealTimeFreshnessViewModel = freshnessDefault(payload) ?? unavailable.freshness;

  return <CurrentMonitorPanel data={data} freshness={freshness} />;
}

export const card38 = (p: any): React.ReactNode => <CurrentMonitorCard payload={p} />;
