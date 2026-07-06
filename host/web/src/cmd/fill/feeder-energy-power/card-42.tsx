import React from "react";
// Card 42 — Load Anomalies (page individual-feeder-meter-shell/energy-power). FRAMES ARE RETIRED: the ONLY data source
// is the Layer-2 completed payload (`{ variant, data: LoadAnomaliesData }` — real neuract series + honest-blank). We
// render LoadAnomaliesChart DIRECTLY from `payload.data`. ALWAYS-DRAWS: an elided/incomplete slice falls back to CMD
// V2's OWN empty-but-valid LoadAnomalies shape (empty series, valid axis, all labels/colours) — never a blank/null
// card, never a fabricated seed.
import { LoadAnomaliesChart } from "@cmd-v2/components/charts/primitives";
import { loadAnomaliesData } from "./view-model";
import { periodToDateWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

/** Card 42 — Load Anomalies: LoadAnomaliesChart fed `payload.data`. Its header PeriodSelect drives a per-card re-fetch
 *  via onDateChange. */
function LoadAnomaliesFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  const data = loadAnomaliesData(payload); // never null — real slice or CMD V2's empty-but-valid shape
  return (
    <LoadAnomaliesChart
      data={data}
      onPeriodChange={(period: string) => onDateChange?.(periodToDateWindow(period))}
    />
  );
}

export const card42 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <LoadAnomaliesFill payload={p} onDateChange={od} />
);
