import React from "react";
// Card 81 — Tap Activity & Wear (page transformer-asset-dashboard/tap-rtcc, CMD V2 TapRtccTab). TapActivityCard fed its
// OWN Layer-2 payload's `activity` slice: hourly tap-operation bars + the lifetime cumulative counter line.
// (The catalog's stale title for this slot is "Loss Analysis"; the tap-rtcc tab's fourth card is Tap Activity & Wear.)
//
// host-served is RETIRED → the payload IS the render source. DOMAIN slot (hourly tap ops + lifetime wear counter have no
// neuract column today) → HONEST-BLANK: when the payload carries no usable activity slice, `activityVM` yields the tab's
// OWN empty chrome (points [], KPI/legend '—', valid axes/labels/colours) — the chart frame STILL DRAWS, never a
// blank/null card, never a fabricated seed (chart-math scalars finitized). The header SamplingPicker drives a per-chart
// re-fetch via onRequest → onDateChange.
import { TapActivityCard } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/TapActivityCard";
import type { ChartFilterParams } from "@cmd-v2/realtime/assetPageSocket";
import { activityVM } from "./view-model";
import { chartParamsToDateWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

function TapActivityFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  return (
    <TapActivityCard
      vm={activityVM(payload)}
      onRequest={(_chart: string, params: ChartFilterParams) =>
        onDateChange?.(chartParamsToDateWindow(params))
      }
    />
  );
}

export const card81 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <TapActivityFill payload={p} onDateChange={od} />
);
