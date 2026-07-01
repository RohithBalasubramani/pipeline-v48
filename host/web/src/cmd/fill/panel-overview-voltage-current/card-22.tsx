import React from "react";
// Card 22 · Other Panels Table — lt-pcc panel-overview Voltage&Current tab.

import { OtherPanelsTable } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type {
  EventMode,
  PeriodBucket,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";

import { panelVcViewModel, selectPeriod, selectPanelId } from "./view-model";

function TableCard({ table, frame }: { table: any; frame?: any }) {
  let period: PeriodBucket = table.period;
  let selectedPanelId: string = table.selectedPanelId;
  try {
    const data = panelVcViewModel(frame);
    if (data) {
      const sel = selectPeriod(data);
      period = sel.period;
      selectedPanelId = selectPanelId(data, period);
    }
  } catch { /* keep seed */ }
  // GUARD: OtherPanelsTable passes `rows={period.panels}` to DataTable, which reads rows.length / rows.map / rows.reduce;
  // Layer 2 elides the panels leaf from the seed payload, so render a placeholder instead of crashing on `.length` of undefined.
  if (!period || !Array.isArray(period.panels)) return null;
  return (
    <div className="h-full">
      <OtherPanelsTable
        pres={table.pres}
        period={period}
        mode={(table.mode ?? null) as EventMode | null}
        selectedPanelId={selectedPanelId}
        onPanelSelect={() => undefined}
      />
    </div>
  );
}

export const card22 = (p: any, f?: any): React.ReactNode =>
  p?.table ? <TableCard table={p.table} frame={f} /> : null;
