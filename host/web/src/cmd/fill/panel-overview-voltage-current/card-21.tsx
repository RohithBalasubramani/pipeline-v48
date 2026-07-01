import React from "react";
// Card 21 · Current Distribution (radar) — lt-pcc panel-overview Voltage&Current tab.

import { CurrentDistributionCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type { PeriodBucket } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";

import { panelVcViewModel, selectPeriod, selectPanelId } from "./view-model";

function DistributionCard({ distribution, frame }: { distribution: any; frame?: any }) {
  let period: PeriodBucket = distribution.period;
  let selectedPanelId: string = distribution.selectedPanelId;
  try {
    const data = panelVcViewModel(frame);
    if (data) {
      const sel = selectPeriod(data);
      period = sel.period;
      selectedPanelId = selectPanelId(data, period);
    }
  } catch { /* keep seed */ }
  // GUARD: CurrentDistributionCard does `period.panels.filter(...).map(...)` to build radar spokes; Layer 2 elides the
  // panels leaf from the seed payload, so render a placeholder instead of crashing on `.filter` of undefined.
  if (!period || !Array.isArray(period.panels)) return null;
  return (
    <div className="h-full">
      <CurrentDistributionCard pres={distribution.pres} period={period} selectedPanelId={selectedPanelId} />
    </div>
  );
}

export const card21 = (p: any, f?: any): React.ReactNode =>
  p?.distribution ? <DistributionCard distribution={p.distribution} frame={f} /> : null;
