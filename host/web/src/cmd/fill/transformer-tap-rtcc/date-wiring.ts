// SamplingPicker ChartFilterParams → host date_window mapping for the two tap-rtcc chart cards.
//
// VoltageRegulationCard + TapActivityCard each carry a SamplingPicker whose selection the card resolves through the
// tab's OWN `tapSelectionToReq` (config.ts) into a backend `{ range, sampling, shift }` — the CMD V2 vocabulary
// (range: today|yesterday|last_7d|this_month|last_month, sampling: hour|shift|day|week). Those arrive here via the
// card's `onRequest(chart, params)`; we translate them into the host window vocabulary the host re-fetches
// JUST this card's frame against — mirroring the feeder date-wiring:
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
import type { ChartFilterParams } from "@cmd-v2/realtime/assetPageSocket";
import type { DateWindow } from "./types";

/** CMD V2 backend range token → host range token. */
function rangeToHost(range?: string): string {
  switch (String(range ?? "").toLowerCase()) {
    case "yesterday":
      return "yesterday";
    case "last_7d":
    case "this_week":
    case "last_week":
      return "last-7-days";
    case "this_month":
    case "last_month":
    case "last_30d":
      return "this-month";
    default:
      return "today"; // "today" + anything unknown
  }
}

/** CMD V2 backend sampling token → host sampling token. `hour` → the detail-tab hourly bucket; `shift` → shift buckets;
 *  the multi-day coarse buckets (`day`/`week`) pass through unchanged (same vocabulary on both sides). */
function samplingToHost(sampling?: string): string {
  switch (String(sampling ?? "").toLowerCase()) {
    case "shift":
      return "shift";
    case "day":
      return "day";
    case "week":
      return "week";
    case "hour":
    case "hourly":
    default:
      return "hourly";
  }
}

/** Map a chart card's `ChartFilterParams` (from `tapSelectionToReq`) → the host date_window that re-fetches this
 *  card's frame. `shift` is not part of the host window vocabulary (the host re-fetch keys on range+sampling), so it
 *  is dropped — a `shift` sampling still re-buckets to the shift resolution. */
export function chartParamsToDateWindow(params: ChartFilterParams): DateWindow {
  return { range: rangeToHost(params.range), sampling: samplingToHost(params.sampling) };
}
