import React from "react";
// Card 79 — Voltage Regulation Timeline (page transformer-asset-dashboard/tap-rtcc, CMD V2 TapRtccTab).
// VoltageRegulationCard fed its OWN Layer-2 payload's `regulation` slice: the regulated bus-voltage timeline + OLTC step
// line + AVR dead-band overlay.
//
// host-served is RETIRED → the payload IS the render source. ELECTRICAL slot (the regulated bus voltage IS a real
// neuract measurement) → this is the card that fills for REAL first: when the payload carries the voltage timeline,
// `regulationVM` renders it. ALWAYS-DRAWS: a payload with no usable regulation slice renders the tab's OWN empty chrome
// (points [], KPI/legend '—', valid axes/labels/colours) — the chart frame STILL DRAWS, never a blank/null card, never a
// fabricated seed (chart-math scalars finitized, so a '—' never becomes NaN geometry). The header SamplingPicker drives
// a per-chart re-fetch via onRequest → onDateChange.
import { VoltageRegulationCard } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/VoltageRegulationCard";
import type { ChartFilterParams } from "@cmd-v2/realtime/assetPageSocket";
import { regulationVM } from "./view-model";
import { chartParamsToDateWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

function VoltageRegulationFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  return (
    <VoltageRegulationCard
      vm={regulationVM(payload)}
      onRequest={(_chart: string, params: ChartFilterParams) =>
        onDateChange?.(chartParamsToDateWindow(params))
      }
    />
  );
}

export const card79 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <VoltageRegulationFill payload={p} onDateChange={od} />
);
