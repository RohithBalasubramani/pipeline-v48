/**
 * card 26 — PqFeederTable.
 *
 * payload.table = { pres, period, selectedPanelId }. Live: the priority-rows
 * table-period + its default selected feeder.
 */
import React from "react";

import { PqFeederTable } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import {
  buildHpqPresentation,
  buildPQPeriods,
  defaultPanelIdForFocus,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type { PQPeriod } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { lastPeriod, liveTablePeriod, presentation } from "./derive";
import { noop } from "./noop";
import { snapshotFromFrame } from "./snapshot";

export function renderFeederTable(payload: any, frame?: any): React.ReactNode {
  const args = payload?.table ?? payload ?? {};
  const pres = args.pres ?? buildHpqPresentation().feederTable;
  let period: PQPeriod | undefined = args.period;
  let selectedPanelId: string = args.selectedPanelId ?? "";

  try {
    const snap = snapshotFromFrame(frame);
    if (snap) {
      const fullPres = presentation(snap);
      const selected = lastPeriod(snap.periods);
      if (selected) {
        const tablePeriod = liveTablePeriod(snap, selected);
        period = tablePeriod;
        selectedPanelId = defaultPanelIdForFocus(
          tablePeriod,
          fullPres.aiSummary.defaultFocusKey,
          fullPres.limits,
        );
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

  return (
    <div className="h-full min-h-0">
      <PqFeederTable
        pres={pres}
        period={period}
        selectedPanelId={selectedPanelId}
        onPanelSelect={noop}
      />
    </div>
  );
}
