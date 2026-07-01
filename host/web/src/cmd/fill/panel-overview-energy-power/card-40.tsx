import React from "react";
import { PowerEnergyAnalysisChart } from "@cmd-v2/pages/electrical/tabs/energy-power/PowerEnergyAnalysisChart";
import { periodStringToWindowRange } from "./dateWiring";
import type { DateWindow } from "./types";

// Card 40 — Power Energy Analysis chart (equipment-detail tab). story render: probe(args.data) →
//   <PowerEnergyAnalysisChart data onPeriodChange/>. No faithful live bridge on this aggregate page
//   (its mapper needs a column-row + history socket pair and bails on pcc_panel) → seed-degrade.
export const card40 = (
  payload: any,
  _frame?: any,
  onDateChange?: (dw: DateWindow) => void,
): React.ReactNode => {
  const data = payload?.data ?? payload;
  // Guard: PowerEnergySvg (default active-reactive view) maps data.bars + data.hourlyAverage; Layer 2 elides these
  // data leaves from the seed → .map(undefined) crash. null → clean placeholder instead of a red render error.
  if (!data || !Array.isArray(data.bars) || data.bars.length === 0 || !Array.isArray(data.hourlyAverage)) return null;
  return (
    <PowerEnergyAnalysisChart
      data={data}
      onPeriodChange={(period: string) =>
        onDateChange?.({ range: periodStringToWindowRange(period), sampling: "hourly" })
      }
    />
  );
};
