import React from "react";
// Card 44 — Voltage History (page individual-feeder-meter-shell/voltage-current, CMD V2 Equipment-Detail
// "Voltage & Current" tab). FRAMES ARE RETIRED: the ONLY data source is the Layer-2 completed payload
// (real neuract values + honest-blank '—', shape = the Storybook story args `{ variant, history: { data } }`).
// We render HistoryPanel DIRECTLY from `payload.history.data`, guarded by sanitizeHistory. Honest-degrade:
// a payload with no series leaf falls back to CMD V2's OWN structured-empty HistoryPanelData (series [],
// stats "—") so the panel draws its chrome + dashes — never a blank/null card, never an SVG NaN.
import { HistoryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel";
import { historyData, sanitizeHistory, unavailableHistory } from "./payload-unwrap";
import { withDateControl } from "./date-wiring";
import type { OnDateChange } from "./types";

/** Card 44 — Voltage History: HistoryPanel fed the payload's `history.data`. Its header SamplingPicker
 *  drives a per-card re-fetch via onDateChange. */
function VoltageHistoryCard({
  payload,
  onDateChange,
}: {
  payload: any;
  onDateChange?: OnDateChange;
}) {
  const slice = historyData(payload);
  // ALWAYS-DRAW: use the payload slice when it carries a series; else CMD V2's OWN structured-empty slice (series [],
  // stats "—") so the panel draws its chrome instead of a blank/null card. NEVER return null. sanitizeHistory then
  // guards whichever won: every mapped array is an array and every scalar hitting a scale/Math op is finite, so a
  // per-leaf-elided ('—'/null) value blanks that leaf (gap / dropped ref-line), never NaN.
  const usable = (d: any) => !!d && Array.isArray(d.series);
  const data = sanitizeHistory(usable(slice) ? slice! : unavailableHistory("voltage"));
  return <HistoryPanel data={withDateControl(data, onDateChange)} />;
}

export const card44 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <VoltageHistoryCard payload={p} onDateChange={od} />
);
