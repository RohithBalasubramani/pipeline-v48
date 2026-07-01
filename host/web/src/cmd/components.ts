import type React from "react";

import { DistortionProfileChart as Cmp29 } from "@cmd-v2/components/charts/primitives/DistortionProfileChart";
import { LoadAnomaliesChart as Cmp25 } from "@cmd-v2/components/charts/primitives/LoadAnomaliesChart";
import { LoadImpactChart as Cmp30 } from "@cmd-v2/components/charts/primitives/LoadImpactChart";
import { TodaysEnergyCard as Cmp22 } from "@cmd-v2/components/charts/primitives/TodaysEnergyCard";
import { EnergyInputDistributionCard as Cmp5 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/EnergyInputDistributionCard";
import { DemandProfileCard as Cmp8, EnergyProgressCard as Cmp6, EnergyTrendCard as Cmp7 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/Cards";
import { PqAiSummaryCard as Cmp16, PqFeederTable as Cmp17, PqTimelineCard as Cmp15, PqTopStrip as Cmp14, SignatureCard as Cmp18 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import { RealTimeMonitoringRail as Cmp1 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRail";
import { QuickStats as Cmp4, SupplyCard as Cmp2, TrendCard as Cmp3 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRailCards";
import { AiSummaryCard as Cmp10, CurrentDistributionCard as Cmp12, EventTimelineCard as Cmp11, OtherPanelsTable as Cmp13 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import { EventsTopStrip as Cmp9 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventsTopStrip";
import { InputOutputEnergyCard as Cmp24 } from "@cmd-v2/pages/electrical/tabs/energy-power/InputOutputEnergyCard";
import { PowerEnergyAnalysisChart as Cmp23 } from "@cmd-v2/pages/electrical/tabs/energy-power/PowerEnergyAnalysisChart";
import { PowerQualityCard as Cmp28 } from "@cmd-v2/pages/electrical/tabs/power-quality/PowerQualityCard";
import { CurrentMonitorPanel as Cmp21 } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/CurrentMonitorPanel";
import { PowerEnergyPanel as Cmp19 } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/PowerEnergyPanel";
import { VoltageMonitorPanel as Cmp20 } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/VoltageMonitorPanel";
import { HealthSummaryPanel as Cmp26 } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { HistoryPanel as Cmp27 } from "@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel";

// card_id -> REAL CMD_V2 component (generated from /tmp/wire_recipes.json). renderCmd hands it the unwrapped payload.
export const COMPONENTS: Record<number, React.ComponentType<any>> = {
  7: Cmp1,
  9: Cmp2,
  10: Cmp3,
  11: Cmp4,
  12: Cmp5,
  14: Cmp6,
  15: Cmp6,
  16: Cmp7,
  17: Cmp8,
  18: Cmp9,
  19: Cmp10,
  20: Cmp11,
  21: Cmp12,
  22: Cmp13,
  23: Cmp14,
  24: Cmp15,
  25: Cmp16,
  26: Cmp17,
  27: Cmp18,
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
