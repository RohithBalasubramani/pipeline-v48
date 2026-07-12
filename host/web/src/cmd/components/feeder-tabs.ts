import type React from "react";

// EQUIPMENT-DETAIL / FEEDER deep-tab family barrel (cards 36–49) — card_id → REAL CMD_V2 component, discovered by
// ./index.ts.
import { DistortionProfileChart as Cmp29 } from "@cmd-v2/components/charts/primitives/DistortionProfileChart";
import { LoadAnomaliesChart as Cmp25 } from "@cmd-v2/components/charts/primitives/LoadAnomaliesChart";
import { LoadImpactChart as Cmp30 } from "@cmd-v2/components/charts/primitives/LoadImpactChart";
import { TodaysEnergyCard as Cmp22 } from "@cmd-v2/components/charts/primitives/TodaysEnergyCard";
import { InputOutputEnergyCard as Cmp24 } from "@cmd-v2/pages/electrical/tabs/energy-power/InputOutputEnergyCard";
import { PowerEnergyAnalysisChart as Cmp23 } from "@cmd-v2/pages/electrical/tabs/energy-power/PowerEnergyAnalysisChart";
import { PowerQualityCard as Cmp28 } from "@cmd-v2/pages/electrical/tabs/power-quality/PowerQualityCard";
import { CurrentMonitorPanel as Cmp21 } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/CurrentMonitorPanel";
import { PowerEnergyPanel as Cmp19 } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/PowerEnergyPanel";
import { VoltageMonitorPanel as Cmp20 } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/VoltageMonitorPanel";
import { HealthSummaryPanel as Cmp26 } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { HistoryPanel as Cmp27 } from "@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel";

export const COMPONENTS: Record<number, React.ComponentType<any>> = {
  36: Cmp19,
  37: Cmp20,
  38: Cmp21,
  39: Cmp22,
  40: Cmp23,
  41: Cmp24,
  42: Cmp25,
  43: Cmp26,
  44: Cmp27,
  45: Cmp26,
  46: Cmp27,
  47: Cmp28,
  48: Cmp29,
  49: Cmp30,
};
