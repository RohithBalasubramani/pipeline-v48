import React from "react";
// Card 46 — Current History (page individual-feeder-meter-shell/voltage-current, CMD V2 Equipment-Detail
// "Voltage & Current" tab). FRAMES ARE RETIRED: the ONLY data source is the Layer-2 completed payload
// (real neuract values + honest-blank '—', shape = the Storybook story args `{ variant, history: { data } }`).
// We render HistoryPanel DIRECTLY from `payload.history.data`, guarded by sanitizeHistory. Honest-degrade:
// a payload with no series leaf falls back to CMD V2's OWN structured-empty HistoryPanelData (series [],
// stats "—") so the panel draws its chrome + dashes — never a blank/null card, never an SVG NaN.
import { HistoryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel";
import { historyData, sanitizeHistory, unavailableHistory } from "./payload-unwrap";
import { withDateControl } from "./date-wiring";
import type { OnDateChange } from "./types";

/** Card 46 — Current History: HistoryPanel fed the payload's `history.data`. Its header SamplingPicker
 *  drives a per-card re-fetch via onDateChange. */
function CurrentHistoryCard({
  payload,
  onDateChange,
}: {
  payload: any;
  onDateChange?: OnDateChange;
}) {
  const slice = historyData(payload);
  // ALWAYS-DRAW: use the payload slice when it carries a series; else CMD V2's OWN structured-empty slice so the panel
  // draws chrome + "—" instead of a blank/null card. sanitizeHistory guards whichever won: a server honest-dashed
  // scalar ('—' on maxLine/minLine.value, a series bucket, a yTick) can NEVER reach HistoryPanel's yScale/Math.round
  // and emit an SVG NaN — the elided leaf blanks (dropped ref-line / line gap) instead. Matches card 44's idiom.
  const usable = (d: any) => !!d && Array.isArray(d.series);
  const data = sanitizeHistory(usable(slice) ? slice! : unavailableHistory("current"));
  return <HistoryPanel data={withDateControl(data, onDateChange)} />;
}

export const card46 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <CurrentHistoryCard payload={p} onDateChange={od} />
);
