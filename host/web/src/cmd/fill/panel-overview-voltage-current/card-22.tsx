import React from "react";
// Card 22 · Other Panels Table — lt-pcc panel-overview Voltage&Current tab.
//
// PAYLOAD-DIRECT (ems_backend RETIRED — `frame` is always empty now). Priority:
// payload → CMD V2 HONEST-EMPTY view-model. OtherPanelsTable feeds `rows={period.panels}`
// to DataTable (rows.length/map/reduce); if the payload elided the panels leaf, fall back to
// the page's OWN honest-empty model (empty panels, chrome only, NO fabrication). NEVER null.
// The old live-aggregate-frame branch is dead code and was DELETED.

import { OtherPanelsTable } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type {
  EventMode,
  PeriodBucket,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";

import {
  bundleFrom,
  fallbackViewModel,
  defaultPresentation,
  hasPanels,
} from "./view-model";

function TableCard({ table }: { table: any }) {
  // 1) payload (Layer-2 completed — real or honest-blank).
  let period: PeriodBucket = table?.period;
  let selectedPanelId: string = table?.selectedPanelId;

  // 2) DRAW GUARANTEE — backfill panel-bearing period + selected id from the honest-empty model.
  if (!hasPanels(period)) {
    const b = bundleFrom(fallbackViewModel());
    period = b.period;
    selectedPanelId = selectedPanelId || b.selectedPanelId;
  }
  if (!selectedPanelId) selectedPanelId = period.panels[0]?.id ?? "";

  const pres = table?.pres ?? defaultPresentation().otherPanelsTable;
  return (
    <div className="h-full">
      <OtherPanelsTable
        pres={pres}
        period={period}
        mode={(table?.mode ?? null) as EventMode | null}
        selectedPanelId={selectedPanelId}
        onPanelSelect={() => undefined}
      />
    </div>
  );
}

export const card22 = (p: any): React.ReactNode =>
  <TableCard table={p?.table} />;
