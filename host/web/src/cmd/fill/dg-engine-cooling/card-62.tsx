import React from "react";
// Card 62 — Pressure · Speed · Load (page diesel-generator-asset-dashboard/engine-cooling). Renders CMD V2's REAL
// <Panel> (EngineHistoryCharts.tsx) with the `mech` ChartVM (oil pressure kPa left-axis, engine speed + load% right
// axis, expected-pressure band, low-oil-P limit pill, event rail) fed a full EngineCoolingViewModel built off the
// Layer-2 payload {chart}.
//
// FRAMES=PAYLOADS [architecture]: ems_backend is RETIRED (frames={} EMPTY), so there is no live-frame / mapper path.
// oil pressure + engine speed + load% are ENGINE-DOMAIN telemetry — no neuract columns — so Layer-2 carries no series
// points. engineCoolingViewModel overlays the payload's real `chart` chrome (title/KPIs/legend/insight — real or
// honest-blank '—') onto CMD V2's OWN typed-empty view-model (series present, EMPTY points). The card STILL DRAWS its
// full structure as an honest empty timeline — never a blank/null card and never CMD V2's demo telemetry
// (getEngineMockFrame). The EngineDatePicker baked inside <Panel> is cosmetic; the host wires no onDateChange.
import { Panel } from "@cmd-v2/pages/assets/diesel-generator/tabs/engine-cooling/EngineHistoryCharts";
import { EngineHoverProvider } from "@cmd-v2/pages/assets/diesel-generator/tabs/engine-cooling/EngineHover";
import { engineCoolingViewModel } from "./view-model";

function PressureSpeedLoadFill({ payload }: { payload: any }) {
  const vm = engineCoolingViewModel(payload, "mech"); // never null — Layer-2 chrome over CMD V2's typed-empty vm
  return (
    <EngineHoverProvider>
      <Panel vm={vm} chart={vm.charts.mech} />
    </EngineHoverProvider>
  );
}

export const card62 = (p: any): React.ReactNode => <PressureSpeedLoadFill payload={p} />;
