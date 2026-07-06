import React from "react";
// Card 67 — Voltage History (page diesel-generator-asset-dashboard/voltage-current, CMD V2 DG "Voltage & Current" tab).
// HistoryPanel fed its OWN Layer-2 payload's voltage `data` (HistoryPanelData).
//
// ems_backend is RETIRED → the payload IS the render source. The harvested story args are `{ variant, data:
// HistoryPanelData }` (real neuract series + honest-blank '—'), so we read `payload.data` straight. Honest-degrade: a
// payload with no usable HistoryPanelData (Layer 2 elided the series leaf) falls back to CMD V2's OWN structured-empty
// slice — NEVER a blank/null card, NEVER a mock/seed number. Its header SamplingPicker drives a per-card re-fetch via
// onDateChange.
import { HistoryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel";
import { unavailableHistory } from "./empty-view-model";
import { historyData, sanitizeHistory } from "./payload-unwrap";
import { withDateControl } from "./date-wiring";
import type { OnDateChange } from "./types";

function VoltageHistoryCard({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  const fromPayload = historyData(payload);
  // ALWAYS-DRAW: prefer the payload's HistoryPanelData; if unusable (Layer 2 elided the series leaf), fall back to CMD
  // V2's OWN structured-empty slice (series [], stats '—') so the panel draws its chrome instead of a blank/null card.
  const usable = (d: any) => !!d && Array.isArray(d.series);
  const data = usable(fromPayload) ? fromPayload! : unavailableHistory("voltage");
  // sanitizeHistory: per-leaf guard-rail (all mapped arrays guaranteed, scaled scalars finitized, '—' bucket → null gap,
  // non-finite ref-lines dropped) — see payload-unwrap.
  return <HistoryPanel data={withDateControl(sanitizeHistory(data), onDateChange)} />;
}

export const card67 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <VoltageHistoryCard payload={p} onDateChange={od} />
);
