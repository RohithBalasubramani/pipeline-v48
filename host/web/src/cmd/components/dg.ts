import type React from "react";

// DIESEL-GENERATOR asset-dashboard family barrel (cards 66–72 subset, direct payload render) — discovered by
// ./index.ts. Ids 61/62/63/64/65/71/73 are NOT here: they need a module-default view-model the payload lacks (or
// carry no Storybook payload) → the FILL fallback (../fill/dg-*.tsx); 60 is a viewer envelope (SPECIAL).
// DG · fuel-efficiency (runs → RunsList needs default vm.runs → FILL fallback, not here)
// DG · voltage-current (data) — reuses the electrical HealthSummaryPanel / HistoryPanel
import { LiveOpsCard as Cmp70 } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/LiveOpsCard";
import { EnergyReliabilityCard as Cmp72 } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/EnergyReliabilityCard";
import { HealthSummaryPanel as CmpHS } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { HistoryPanel as CmpHP } from "@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel";

export const COMPONENTS: Record<number, React.ComponentType<any>> = {
  66: CmpHS, // DG voltage health — HealthSummaryPanel
  67: CmpHP, // DG voltage history — HistoryPanel
  68: CmpHS, // DG current health — HealthSummaryPanel
  69: CmpHP, // DG current history — HistoryPanel
  70: Cmp70,
  72: Cmp72,
};
