import React from "react";
// Card 76 — Thermal Timeline (page transformer-asset-dashboard/thermal-life). ThermalTimelineCard fed its OWN Layer-2
// payload's `timeline` slice → today's hotspot/oil/load/efficiency series.
//
// ems_backend is RETIRED → the payload IS the render source. ALWAYS-DRAWS [GOAL]: the load% + efficiency series are
// electrical-derivable and plot REAL from the payload; the hotspot/oil temperature lines are domain readings that read
// flat/empty when neuract has no column. A payload with no usable timeline series renders the tab's OWN typed-empty
// view-model (single '—' bucket → flat blank line, valid axes/legend) — the chart STILL DRAWS, never a blank/null card
// and never a fabricated seed (every plotted scalar finitized; the component `.toFixed`es each one). Its header
// SamplingPicker (today × 3-hourly ↔ hourly) drives a per-card re-fetch via onDateChange.
import { ThermalTimelineCard } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/ThermalTimelineCard";
import { timelineVM } from "./view-model";
import { reqToDateWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

function ThermalTimelineFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  return (
    <ThermalTimelineCard
      vm={timelineVM(payload)}
      onRequest={(_chart, params) => onDateChange?.(reqToDateWindow(params))}
    />
  );
}

export const card76 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <ThermalTimelineFill payload={p} onDateChange={od} />
);
