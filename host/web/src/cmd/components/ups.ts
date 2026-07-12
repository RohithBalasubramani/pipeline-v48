import type React from "react";

// UPS asset-dashboard family barrel (cards 50–59, direct payload render) — discovered by ./index.ts.
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

export const COMPONENTS: Record<number, React.ComponentType<any>> = {
  50: Cmp50,
  51: Cmp51,
  52: Cmp52,
  53: Cmp51, // Backup Readiness History — same ScoreHistoryCard as 51
  54: Cmp54,
  55: Cmp55,
  56: Cmp56,
  57: Cmp57,
  58: Cmp58,
  59: Cmp56, // CompositeChartCard reused
};
