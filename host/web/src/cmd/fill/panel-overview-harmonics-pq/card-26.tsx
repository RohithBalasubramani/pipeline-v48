/**
 * card 26 — PqFeederTable.
 *
 * PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). The Layer-2
 * completed payload IS the render source: payload.table = { pres, period, selectedPanelId },
 * carrying REAL per-feeder priority rows or honest-blank. The old live snapshotFromFrame(frame)
 * branch AND the buildPQPeriods() fabrication fallback (synthetic harmonic waves — a seed leak)
 * are DELETED. PqFeederTable feeds `rows={period.panels}` to DataTable, so an empty period
 * (`panels: []`) renders an honest-empty table (chrome + no rows), NEVER a mock.
 */
import React from "react";

import { PqFeederTable } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import { buildHpqPresentation } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type { PQPeriod } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { emptyPeriod } from "./derive";
import { noop } from "./noop";

export function renderFeederTable(payload: any): React.ReactNode {
  const args = payload?.table ?? payload ?? {};
  const pres = args.pres ?? buildHpqPresentation().feederTable;
  const period: PQPeriod = args.period ?? emptyPeriod();
  const selectedPanelId: string = args.selectedPanelId ?? period.panels[0]?.id ?? "";

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
