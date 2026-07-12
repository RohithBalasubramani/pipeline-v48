import type React from "react";

// PANEL-OVERVIEW family barrel (cards 7–27 + 13) — card_id → REAL CMD_V2 component, discovered by ./index.ts.
import { EnergyInputDistributionCard as Cmp5 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/EnergyInputDistributionCard";
import { EnergyFlowDiagramCard as CmpEF13 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/EnergyFlowDiagramCard";
import { DemandProfileCard as Cmp8, EnergyProgressCard as Cmp6, EnergyTrendCard as Cmp7 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/Cards";
import { PqAiSummaryCard as Cmp16, PqFeederTable as Cmp17, PqTimelineCard as Cmp15, PqTopStrip as Cmp14, SignatureCard as Cmp18 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import { RealTimeMonitoringRail as Cmp1 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRail";
import { QuickStats as Cmp4, SupplyCard as Cmp2, TrendCard as Cmp3 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRailCards";
import { AiSummaryCard as Cmp10, CurrentDistributionCard as Cmp12, EventTimelineCard as Cmp11, OtherPanelsTable as Cmp13 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import { EventsTopStrip as Cmp9 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventsTopStrip";
import { withSectionSplit } from "../section-split";

export const COMPONENTS: Record<number, React.ComponentType<any>> = {
  7: Cmp1,
  9: Cmp2,
  10: Cmp3,
  11: Cmp4,
  12: Cmp5,
  13: CmpEF13, // Energy Flow Diagram (direct payload render)
  14: Cmp6,
  15: Cmp6,
  16: Cmp7,
  17: Cmp8,
  18: Cmp9,
  19: Cmp10,
  20: withSectionSplit(Cmp11), // sections-aware: a bus-section compare renders per-section series [sections overlay]
  21: Cmp12,
  22: Cmp13,
  23: Cmp14,
  24: Cmp15,
  25: Cmp16,
  26: Cmp17,
  27: Cmp18,
};
