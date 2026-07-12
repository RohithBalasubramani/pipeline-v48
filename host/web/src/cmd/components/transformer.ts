import type React from "react";

// TRANSFORMER asset-dashboard family barrel (cards 74–81, direct payload render, vm prop) — discovered by ./index.ts.
import { ThermalLifeCard as Cmp74 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/ThermalLifeCard";
import { LifeCapacityCard as Cmp75 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/LifeCapacityCard";
import { ThermalTimelineCard as Cmp76 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/ThermalTimelineCard";
import { InsulationAgingCard as Cmp77 } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/InsulationAgingCard";
import { TapPositionCard as Cmp78 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/TapPositionCard";
import { VoltageRegulationCard as Cmp79 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/VoltageRegulationCard";
import { RecentTapChangesCard as Cmp80 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/RecentTapChangesCard";
import { TapActivityCard as Cmp81 } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/TapActivityCard";

export const COMPONENTS: Record<number, React.ComponentType<any>> = {
  74: Cmp74,
  75: Cmp75,
  76: Cmp76,
  77: Cmp77,
  78: Cmp78,
  79: Cmp79,
  80: Cmp80,
  81: Cmp81,
};
