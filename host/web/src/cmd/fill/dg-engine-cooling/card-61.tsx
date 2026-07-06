import React from "react";
// Card 61 — Thermal Timeline (page diesel-generator-asset-dashboard/engine-cooling). Renders CMD V2's REAL <Panel>
// (EngineHistoryCharts.tsx) with the thermal ChartVM (coolant/oil/intake/exhaust °C, dual axes, expected band,
// warn/trip lines, event rail) fed a full EngineCoolingViewModel built off the Layer-2 payload {chart}.
//
// FRAMES=PAYLOADS [architecture]: ems_backend is RETIRED (frames={} EMPTY), so there is no live-frame / mapper path.
// engine thermal telemetry is ENGINE-DOMAIN — there are NO neuract columns for it — so Layer-2 carries no series
// points. engineCoolingViewModel overlays the payload's real `chart` chrome (title/KPIs/legend/insight — real or
// honest-blank '—') onto CMD V2's OWN typed-empty view-model (all series present, EMPTY points). The card STILL DRAWS
// its full structure (axes/band/legend/KPIs) as an honest empty timeline — never a blank/null card and never CMD V2's
// demo telemetry (getEngineMockFrame). A cosmetic EngineDatePicker is baked inside <Panel>; the host wires no
// onDateChange (no re-fetchable history endpoint for this domain).
import { Panel } from "@cmd-v2/pages/assets/diesel-generator/tabs/engine-cooling/EngineHistoryCharts";
import { EngineHoverProvider } from "@cmd-v2/pages/assets/diesel-generator/tabs/engine-cooling/EngineHover";
import { engineCoolingViewModel } from "./view-model";

function ThermalTimelineFill({ payload }: { payload: any }) {
  const vm = engineCoolingViewModel(payload, "thermal"); // never null — Layer-2 chrome over CMD V2's typed-empty vm
  return (
    <EngineHoverProvider>
      <Panel vm={vm} chart={vm.charts.thermal} />
    </EngineHoverProvider>
  );
}

export const card61 = (p: any): React.ReactNode => <ThermalTimelineFill payload={p} />;
