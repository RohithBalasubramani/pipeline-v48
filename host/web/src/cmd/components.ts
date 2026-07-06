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

// ── ASSET cards (ids 13, 50–81): the SAME real CMD_V2 components the fill barrels import, so each renders DIRECTLY from
// its ems_exec-completed payload via <Component {...unwrap(payload)}/> (frames are now empty — the payload IS the props).
// unwrap() aliases the payload's single inner object to whichever single-object prop the card reads (data / vm / view),
// and re-attaches it under its own key + spreads its fields, so every prop shape below is satisfied. [DIRECT-RENDER]
import { EnergyFlowDiagramCard as CmpEF13 } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/EnergyFlowDiagramCard";
// UPS · battery-autonomy (data / data+sampling)
import { BatteryHealthCard as Cmp50 } from "@cmd-v2/pages/assets/ups/tabs/battery-autonomy/BatteryHealthCard";
import { ScoreHistoryCard as Cmp51 } from "@cmd-v2/pages/assets/ups/tabs/battery-autonomy/ScoreHistoryCard";
import { BackupReadinessCard as Cmp52 } from "@cmd-v2/pages/assets/ups/tabs/battery-autonomy/BackupReadinessCard";
// UPS · source-transfer (data / data / view). The composite is the shared primitive CompositeChartCard (view prop).
import { TransferReadinessCard as Cmp54 } from "@cmd-v2/pages/assets/ups/tabs/source-transfer/TransferReadinessCard";
import { ActivityCard as Cmp55 } from "@cmd-v2/pages/assets/ups/tabs/source-transfer/ActivityCard";
import { CompositeChartCard as Cmp56 } from "@cmd-v2/components/charts/primitives";
// UPS · output-load-capacity (view / view / view). Cmp59 reuses the same shared CompositeChartCard primitive.
import { UpsCapacityCard as Cmp57 } from "@cmd-v2/pages/assets/ups/tabs/output-load-capacity/UpsCapacityCard";
import { UpsLoadCard as Cmp58 } from "@cmd-v2/pages/assets/ups/tabs/output-load-capacity/UpsLoadCard";
const Cmp59 = Cmp56;
// DG · fuel-efficiency (runs → RunsList needs default vm.runs → FILL fallback, not here)
// DG · voltage-current (data) — reuses the electrical HealthSummaryPanel / HistoryPanel (Cmp26 / Cmp27)
// DG · operations-runtime (view / view). Cards 71 (needs default vm.runs) & 73 (no Storybook payload) → FILL fallback.
import { LiveOpsCard as Cmp70 } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/LiveOpsCard";
import { EnergyReliabilityCard as Cmp72 } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/EnergyReliabilityCard";
// Transformer · thermal-life (vm / vm / vm / vm)
import { ThermalLifeCard as Cmp74 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/ThermalLifeCard";
import { LifeCapacityCard as Cmp75 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/LifeCapacityCard";
import { ThermalTimelineCard as Cmp76 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/ThermalTimelineCard";
import { InsulationAgingCard as Cmp77 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/InsulationAgingCard";
// Transformer · tap-rtcc (vm / vm / vm / vm)
import { TapPositionCard as Cmp78 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/TapPositionCard";
import { VoltageRegulationCard as Cmp79 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/VoltageRegulationCard";
import { RecentTapChangesCard as Cmp80 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/RecentTapChangesCard";
import { TapActivityCard as Cmp81 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/TapActivityCard";

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
  // ── ASSET cards (direct payload render). Ids 60/61/62/63/64/65/71/73 are NOT here: 60 is a viewer envelope (SPECIAL),
  // and 61/62/63/64/65/71/73 need a module-default view-model the payload lacks (or carry no payload) → FILL fallback.
  13: CmpEF13,
  50: Cmp50,
  51: Cmp51,
  52: Cmp52,
  53: Cmp51, // Backup Readiness History — same ScoreHistoryCard as 51
  54: Cmp54,
  55: Cmp55,
  56: Cmp56,
  57: Cmp57,
  58: Cmp58,
  59: Cmp59,
  66: Cmp26, // DG voltage health — HealthSummaryPanel
  67: Cmp27, // DG voltage history — HistoryPanel
  68: Cmp26, // DG current health — HealthSummaryPanel
  69: Cmp27, // DG current history — HistoryPanel
  70: Cmp70,
  72: Cmp72,
  74: Cmp74,
  75: Cmp75,
  76: Cmp76,
  77: Cmp77,
  78: Cmp78,
  79: Cmp79,
  80: Cmp80,
  81: Cmp81,
};
