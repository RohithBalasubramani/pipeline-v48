// CMD V2 SamplingPicker request → host date_window mapping for the thermal-life history charts.
//
// ThermalTimelineCard + InsulationAgingCard each carry a CMD V2 `SamplingPicker`; its `onRequest(chart, params)` fires
// the ALREADY-MAPPED backend tokens (config.ts `timelineSelectionToReq` / `agingSelectionToReq` emit
// {range: 'today'|'yesterday'|'last_7d'|'this_month'|'last_month', sampling: 'hour'|'hourly'|'day'|'week'}). We forward
// those to the host date-window vocabulary the host re-fetches JUST this card's frame against — mirroring the feeder
// fills' periodToDateWindow, but starting from the picker's backend tokens rather than a label.
import type { DateWindow } from "./types";

/** backend `range` token → host DateWindow.range. (The picker already lowered the preset to a backend token.) */
const RANGE: Record<string, string> = {
  today: "today",
  yesterday: "yesterday",
  last_7d: "last-7-days",
  this_month: "this-month",
  last_month: "last-month",
  "custom-range": "custom-range",
};

/** backend `sampling` token → host DateWindow.sampling. The timeline's "3-Hourly" toggle is the backend `hourly`
 *  (3-hour bucket) and "Hourly" is `hour`; the aging chart uses `day` / `week`. Forward VERBATIM (host understands
 *  the same vocabulary), defaulting unknowns to `day`. */
const SAMPLING: Record<string, string> = {
  hour: "hour",
  hourly: "hourly",
  day: "day",
  week: "week",
};

/** Map a SamplingPicker `onRequest` params object → the host date_window. Unknown tokens fall back to a whole-day
 *  window so a stray pick never sends an unrecognised range/sampling the host can't window on. */
export function reqToDateWindow(params: { range?: string; sampling?: string } | undefined): DateWindow {
  const range = RANGE[String(params?.range ?? "")] ?? "today";
  const sampling = SAMPLING[String(params?.sampling ?? "")] ?? "day";
  return { range, sampling };
}
