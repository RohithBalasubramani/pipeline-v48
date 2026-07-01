import React from "react";
// Card 46 — Current History (page individual-feeder-meter-shell/voltage-current, CMD V2
// Equipment-Detail "Voltage & Current" tab). HistoryPanel fed the LIVE `current-history`
// ems_backend frame, mapped through the page's OWN reducers + mapper + view-model. Honest-degrade:
// a missing/unmappable frame renders the byte-faithful payload default (the Storybook story args).
import { HistoryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel";
import { liveHistory } from "./frame-view-model";
import { historyData } from "./payload-unwrap";
import { withDateControl } from "./date-wiring";
import type { OnDateChange } from "./types";

/** Card 46 — Current History: HistoryPanel fed the live `current-history` frame.
 *  Its header SamplingPicker drives a per-card re-fetch via onDateChange. */
function CurrentHistoryCard({
  payload,
  frame,
  onDateChange,
}: {
  payload: any;
  frame?: any;
  onDateChange?: OnDateChange;
}) {
  const fallback = historyData(payload);
  const live = liveHistory(frame, "current");
  const data = live ?? fallback;
  // GUARD: HistoryPanel indexes data.series[0]; the elided seed payload has none, so render a placeholder if live failed.
  if (!data || !Array.isArray(data.series) || data.series.length === 0) return null;
  return <HistoryPanel data={withDateControl(data, onDateChange)} />;
}

export const card46 = (p: any, f?: any, od?: OnDateChange): React.ReactNode => (
  <CurrentHistoryCard payload={p} frame={f} onDateChange={od} />
);
