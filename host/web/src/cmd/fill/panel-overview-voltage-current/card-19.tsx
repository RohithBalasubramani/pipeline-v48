import React from "react";
// Card 19 · AI Summary — lt-pcc panel-overview Voltage&Current tab.

import { AiSummaryCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type {
  PanelPeriodState,
  PanelPeriodStats,
  PeriodBucket,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";

import { panelVcViewModel, selectPeriod, statsFor, selectPanelId } from "./view-model";

function SummaryCard({ summary, frame }: { summary: any; frame?: any }) {
  let period: PeriodBucket = summary.period;
  let stats: PanelPeriodStats = summary.stats;
  let selectedPanel: PanelPeriodState | undefined = summary.selectedPanel;
  try {
    const data = panelVcViewModel(frame);
    if (data) {
      const sel = selectPeriod(data);
      period = sel.period;
      stats = statsFor(data, period, sel.label);
      const panelId = selectPanelId(data, period);
      selectedPanel = period.panels.find((p: PanelPeriodState) => p.id === panelId) ?? selectedPanel;
    }
  } catch { /* keep seed */ }
  // GUARD: AiSummaryCard → resolveVcAiHeadline → composeVcAiSummaryText does `period.panels.filter(...)`; Layer 2 elides
  // the panels leaf from the seed payload, so render a placeholder instead of crashing on `.filter` of undefined.
  if (!period || !Array.isArray(period.panels)) return null;
  return (
    <div className="h-full">
      <AiSummaryCard pres={summary.pres} period={period} mode={summary.mode ?? "sag"} stats={stats} selectedPanel={selectedPanel} />
    </div>
  );
}

export const card19 = (p: any, f?: any): React.ReactNode =>
  p?.summary ? <SummaryCard summary={p.summary} frame={f} /> : null;
