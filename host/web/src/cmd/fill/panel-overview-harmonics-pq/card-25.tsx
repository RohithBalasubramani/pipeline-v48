/**
 * card 25 — PqAiSummaryCard.
 *
 * payload.summary = { pres, period, focus, stats, selectedPanel }. Live: the
 * selected (last) period + its stats + the default selected feeder.
 */
import React from "react";

import { PqAiSummaryCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import {
  buildHpqPresentation,
  buildPQPeriods,
  defaultPanelIdForFocus,
  periodStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type {
  FocusKey,
  PQPanelState,
  PQPeriod,
  PQStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { lastPeriod, liveTablePeriod, presentation } from "./derive";
import { snapshotFromFrame } from "./snapshot";

export function renderAiSummary(payload: any, frame?: any): React.ReactNode {
  const args = payload?.summary ?? payload ?? {};
  const pres = args.pres ?? buildHpqPresentation().aiSummary;
  let period: PQPeriod | undefined = args.period;
  let stats: PQStats = args.stats;
  let selectedPanel: PQPanelState | undefined = args.selectedPanel;
  const focus: FocusKey | null = (args.focus as FocusKey) ?? null;

  try {
    const snap = snapshotFromFrame(frame);
    if (snap) {
      const fullPres = presentation(snap);
      const selected = lastPeriod(snap.periods);
      if (selected) {
        period = selected;
        stats = periodStats(selected, fullPres.limits);
        const tablePeriod = liveTablePeriod(snap, selected);
        const selectedId = defaultPanelIdForFocus(
          tablePeriod,
          focus ?? fullPres.aiSummary.defaultFocusKey,
          fullPres.limits,
        );
        selectedPanel = tablePeriod.panels.find((p: PQPanelState) => p.id === selectedId);
      }
    }
  } catch {
    /* keep payload defaults */
  }

  if (!period || !stats) {
    const periods = buildPQPeriods();
    const sel = lastPeriod(periods)!;
    period = period ?? sel;
    stats = stats ?? periodStats(sel, buildHpqPresentation().limits);
  }

  return (
    <div className="h-full min-h-0">
      <PqAiSummaryCard
        pres={pres}
        period={period}
        focus={focus}
        stats={stats}
        selectedPanel={selectedPanel}
      />
    </div>
  );
}
