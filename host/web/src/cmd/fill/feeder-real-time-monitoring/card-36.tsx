import React from "react";
// Card 36 — Power & Energy Panel (page individual-feeder-meter-shell/real-time-monitoring,
// CMD V2 RealTimeMonitoringTab).
//
// PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). The Layer-2
// completed payload IS the render source: { data: PowerEnergyViewModel, freshness }
// carrying REAL neuract values or honest-blank '—' per leaf. We render the CMD V2
// PowerEnergyPanel straight from it. The old liveRailVM(frame) reduce→map→viewModel
// path is dead (frame never arrives) and has been DELETED.
//
// HONEST-DEGRADE + ALWAYS-DRAW: when the payload elides `data`/`freshness`, we hand the
// panel the CMD V2 "unavailable" view-model slice (fully structured, empty series → "—",
// NEVER mock numbers — see realTimeMonitoringViewModel FE-1). This card NEVER returns null.
import { PowerEnergyPanel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/PowerEnergyPanel";
import { createUnavailableRealTimeMonitoringViewModel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/realTimeMonitoringViewModel";
import type {
  PowerEnergyViewModel,
  RealTimeFreshnessViewModel,
} from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/types";
import { powerEnergyDefault, freshnessDefault } from "./payload-unwrap";

function PowerEnergyCard({ payload }: { payload: any }) {
  const unavailable = createUnavailableRealTimeMonitoringViewModel();

  // payload → CMD V2 unavailable slice. Both branches are a fully structured
  // PowerEnergyViewModel (dataSeries/readings/railLabels present), so the panel
  // always draws — real numbers from the payload, "—" placeholders otherwise.
  const data: PowerEnergyViewModel = powerEnergyDefault(payload) ?? unavailable.powerEnergy;
  const freshness: RealTimeFreshnessViewModel = freshnessDefault(payload) ?? unavailable.freshness;

  return <PowerEnergyPanel data={data} freshness={freshness} />;
}

export const card36 = (p: any): React.ReactNode => <PowerEnergyCard payload={p} />;
