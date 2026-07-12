import React from "react";
// Card 65 — Fuel & Tank — Composite (page diesel-generator-asset-dashboard/fuel-efficiency). The REAL FuelCompositeCard
// (the single in-house SVG timeline: level / rate / temp + KPI strip + mode strip + AI insight) rendered from a
// FuelEfficiencyViewModel built off the Layer-2 payload {chart}.
//
// FRAMES=PAYLOADS [architecture]: host-served is RETIRED (frames={} EMPTY), so there is no live-frame / mapper path.
// FuelCompositeCard reads `vm.chart` (title/kpis/legend/insight — carried on the Layer-2 payload) AND `vm.points`
// (the plotted numeric series). The fuel history series are DG telemetry neuract does NOT carry, so Layer-2 omits the
// points — fuelCompositeVm overlays the payload's real `chart` chrome onto CMD V2's OWN empty view-model (EMPTY points).
// The composite STILL DRAWS its real chrome (title, axes, mode strip, KPIs, AI-summary) as an honest empty timeline —
// never a null/blank card and never the seed 40% efficiency / ₹26.3 mock numbers.
//
// The composite's crosshair/tooltip read the shared FuelHoverProvider context (exactly how the tab layout + the card's
// own storybook wrap it), so it is mounted here too. FuelCompositeCard's EngineDatePicker is self-contained (no per-card
// re-fetch) — so this card carries no onDateChange.
import { FuelCompositeCard } from "@cmd-v2/pages/assets/diesel-generator/tabs/fuel-efficiency/FuelHistoryCharts";
import { FuelHoverProvider } from "@cmd-v2/pages/assets/diesel-generator/tabs/fuel-efficiency/FuelHover";
import { fuelCompositeVm } from "./view-model";

function FuelCompositeFill({ payload }: { payload: any }) {
  // fuelCompositeVm NEVER returns null — the whole vm is always a drawable, fully-labelled composite (the Layer-2
  // chart chrome overlaid on CMD V2's own empty-but-valid timeline: [] points, real title/KPIs/legend/insight).
  const vm = fuelCompositeVm(payload);
  return (
    <FuelHoverProvider>
      <FuelCompositeCard vm={vm} />
    </FuelHoverProvider>
  );
}

export const card65 = (p: any): React.ReactNode => <FuelCompositeFill payload={p} />;
