/**
 * card 27 — SignatureCard (harmonic-signature radar).
 *
 * payload.signature = { pres, period, selectedPanelId, apiSignature }. Live:
 * the mapper pre-resolves `pres.signature.spokes`/`selectedName` AND ships
 * `apiExtras.signature` (the radar source), which the card consumes directly.
 */
import React from "react";

import { SignatureCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import {
  buildHpqPresentation,
  buildPQPeriods,
  defaultPanelIdForFocus,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type { PQPeriod } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { lastPeriod, liveTablePeriod, presentation } from "./derive";
import { snapshotFromFrame } from "./snapshot";

export function renderSignature(payload: any, frame?: any): React.ReactNode {
  const args = payload?.signature ?? payload ?? {};
  let pres = args.pres ?? buildHpqPresentation().signature;
  let period: PQPeriod | undefined = args.period;
  let selectedPanelId: string = args.selectedPanelId ?? "";
  let apiSignature = args.apiSignature;

  try {
    const snap = snapshotFromFrame(frame);
    if (snap) {
      const fullPres = presentation(snap);
      pres = fullPres.signature;
      const selected = lastPeriod(snap.periods);
      if (selected) {
        const tablePeriod = liveTablePeriod(snap, selected);
        period = tablePeriod;
        selectedPanelId = defaultPanelIdForFocus(
          tablePeriod,
          fullPres.aiSummary.defaultFocusKey,
          fullPres.limits,
        );
        apiSignature = snap.apiExtras?.signature ?? apiSignature;
      }
    }
  } catch {
    /* keep payload defaults */
  }

  if (!period) {
    const periods = buildPQPeriods();
    const sel = lastPeriod(periods)!;
    period = sel;
    if (!selectedPanelId) {
      selectedPanelId = defaultPanelIdForFocus(
        sel,
        buildHpqPresentation().aiSummary.defaultFocusKey,
      );
    }
  }

  // Elided-seed guard: Layer 2 elides `signature.spokes` (a roster array) from the
  // fallback payload, but SignatureCard feeds `pres.spokes` to ComparisonRadarChart
  // which does `spokes.map(...)` unconditionally. A present-but-partial `pres`
  // (missing `spokes`) crashes — render null so the card shows a clean placeholder.
  if (!Array.isArray(pres?.spokes)) return null;

  return (
    <div className="h-full min-h-0">
      <SignatureCard
        pres={pres}
        period={period}
        selectedPanelId={selectedPanelId}
        apiSignature={apiSignature}
      />
    </div>
  );
}
