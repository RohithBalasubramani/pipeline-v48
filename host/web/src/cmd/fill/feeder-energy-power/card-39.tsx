import React from "react";
// Card 39 — Today's Energy (page individual-feeder-meter-shell/energy-power). FRAMES ARE RETIRED: the ONLY data source
// is the Layer-2 completed payload (`{ variant, data: TodaysEnergyData }` — real neuract values + honest-blank '—').
// We render TodaysEnergyCard DIRECTLY from `payload.data`. ALWAYS-DRAWS: an elided slice falls back to CMD V2's OWN
// empty-but-valid Today's-Energy shape — never a blank/null card, never a fabricated seed.
import { TodaysEnergyCard } from "@cmd-v2/components/charts/primitives";
import { todaysEnergyData } from "./view-model";
import { periodToDateWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

/** Card 39 — Today's Energy: TodaysEnergyCard fed `payload.data`. Its header FilterPillSelect drives a per-card
 *  re-fetch via onDateChange. */
function TodaysEnergyFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  const data = todaysEnergyData(payload); // never null — real slice or CMD V2's empty-but-valid shape
  return (
    <TodaysEnergyCard
      data={data}
      onPeriodChange={(period: string) => onDateChange?.(periodToDateWindow(period))}
    />
  );
}

export const card39 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <TodaysEnergyFill payload={p} onDateChange={od} />
);
