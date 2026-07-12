import React from "react";
// Card 19 · AI Summary — lt-pcc panel-overview Voltage&Current tab.
//
// PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). Priority:
// payload → CMD V2 HONEST-EMPTY view-model. The AI-summary component reads period.panels,
// so if the payload elided the panels leaf, we fall back to the page's OWN honest-empty
// model (fallbackViewModel — periods:[], chrome only, NO fabricated data). NEVER null.
// The old live-aggregate-frame branch is dead code and was DELETED.

import { AiSummaryCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type {
  PanelPeriodState,
  PanelPeriodStats,
  PeriodBucket,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";

import {
  bundleFrom,
  fallbackViewModel,
  defaultPresentation,
  hasPanels,
} from "./view-model";

function SummaryCard({ summary, backendAiSummary }: { summary: any; backendAiSummary?: string | null }) {
  // 1) payload (Layer-2 completed — real or honest-blank; may have elided data leaves).
  let period: PeriodBucket = summary?.period;
  let stats: PanelPeriodStats = summary?.stats;
  let selectedPanel: PanelPeriodState | undefined = summary?.selectedPanel;

  // 2) DRAW GUARANTEE — backfill EVERY missing leaf (period.panels / stats /
  //    selectedPanel) from the page's OWN honest-empty model so the card always renders.
  if (!hasPanels(period) || !stats || !selectedPanel) {
    const b = bundleFrom(fallbackViewModel());
    if (!hasPanels(period)) { period = b.period; selectedPanel = selectedPanel ?? b.selectedPanel; }
    stats = stats ?? b.stats;
    selectedPanel = selectedPanel ?? period.panels[0] ?? b.selectedPanel;
  }

  const presBase = summary?.pres ?? defaultPresentation().aiSummary;
  // The executor's REAL grounded narrative (narrative_ai renderer) rides pres.backendHeadline — the component's
  // resolveVcAiHeadline does `backendHeadline ?? composeLocal`, so the real paragraph REPLACES the local
  // composition (which would otherwise recompute from zeroed seed stats). Honest-degrade: absent → local.
  const pres = backendAiSummary ? { ...presBase, backendHeadline: backendAiSummary } : presBase;
  return (
    <div className="h-full">
      <AiSummaryCard pres={pres} period={period} mode={summary?.mode ?? "sag"} stats={stats} selectedPanel={selectedPanel} />
    </div>
  );
}

export const card19 = (p: any): React.ReactNode =>
  <SummaryCard summary={p?.summary}
               backendAiSummary={p?.ai_summary?.text ?? p?.widgets?.ai_summary?.text ?? null} />;
