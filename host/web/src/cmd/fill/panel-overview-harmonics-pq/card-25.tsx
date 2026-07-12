/**
 * card 25 — PqAiSummaryCard.
 *
 * PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). The Layer-2
 * completed payload IS the render source: payload.summary = { pres, period, focus, stats,
 * selectedPanel }, carrying REAL selected-period stats or honest-blank. The old live
 * snapshotFromFrame(frame) branch AND the buildPQPeriods() fabrication fallback (synthetic
 * harmonic waves — a seed leak) are DELETED. A payload that elided period/stats degrades to
 * emptyPeriod()/emptyStats() (honest '—', NEVER a fabricated bucket). The executor's REAL
 * grounded narrative rides backendAiSummary and REPLACES the local composeHpqAiText.
 */
import React from "react";

import { PqAiSummaryCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import { buildHpqPresentation } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type {
  FocusKey,
  PQPanelState,
  PQPeriod,
  PQStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { emptyPeriod, emptyStats } from "./derive";

export function renderAiSummary(payload: any): React.ReactNode {
  const args = payload?.summary ?? payload ?? {};
  // The executor's REAL grounded narrative (narrative_ai renderer). When present it must be what renders —
  // PqAiSummaryCard's backendAiSummary REPLACES the local composeHpqAiText composition, which would otherwise
  // recompute a sentence from the honestly-zeroed seed stats. Honest-degrade: absent → local composition.
  const backendAiSummary: string | null =
    payload?.ai_summary?.text ?? payload?.widgets?.ai_summary?.text ?? null;
  const pres = args.pres ?? buildHpqPresentation().aiSummary;
  const period: PQPeriod = args.period ?? emptyPeriod();
  const stats: PQStats = args.stats ?? emptyStats();
  const selectedPanel: PQPanelState | undefined = args.selectedPanel;
  const focus: FocusKey | null = (args.focus as FocusKey) ?? null;

  return (
    <div className="h-full min-h-0">
      <PqAiSummaryCard
        pres={pres}
        period={period}
        focus={focus}
        stats={stats}
        selectedPanel={selectedPanel}
        backendAiSummary={backendAiSummary}
      />
    </div>
  );
}
