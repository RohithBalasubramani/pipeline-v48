import React from "react";
// Card 40 — Power Energy Analysis (page individual-feeder-meter-shell/energy-power). FRAMES ARE RETIRED: the ONLY data
// source is the Layer-2 completed payload (`{ variant, data: PowerEnergyAnalysisData }` — real neuract bars +
// honest-blank). We render PowerEnergyAnalysisChart DIRECTLY from `payload.data`. ALWAYS-DRAWS: an elided/incomplete
// slice falls back to CMD V2's OWN empty-but-valid PowerAnalysis shape (demandBars [], valid axis) — never a
// blank/null card, never a fabricated seed.
import { PowerEnergyAnalysisChart } from "@cmd-v2/pages/electrical/tabs/energy-power/PowerEnergyAnalysisChart";
import { powerAnalysisData } from "./view-model";
import { periodToDateWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

/** Card 40 — Power Energy Analysis: PowerEnergyAnalysisChart fed `payload.data`. Its header PeriodSelect drives a
 *  per-card re-fetch via onDateChange. */
function PowerEnergyAnalysisFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  const data = powerAnalysisData(payload); // never null — real slice or CMD V2's empty-but-valid shape
  return (
    <PowerEnergyAnalysisChart
      data={data}
      onPeriodChange={(period: string) => onDateChange?.(periodToDateWindow(period))}
    />
  );
}

export const card40 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <PowerEnergyAnalysisFill payload={p} onDateChange={od} />
);
