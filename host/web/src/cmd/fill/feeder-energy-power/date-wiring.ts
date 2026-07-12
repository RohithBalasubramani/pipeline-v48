// period-string → host date_window mapping for the feeder energy-power fill cards.
//
// TodaysEnergyCard's header FilterPillSelect, PowerEnergyAnalysisChart's + LoadAnomaliesChart's PeriodSelect each emit
// a single `period` LABEL string (one of data.periodOptions — "Today" / "This Week" / "This Month", or the mock
// template's "Weekly"/"Monthly"/"Quarterly"). We translate that label → the host window vocabulary the host
// re-fetches JUST this card's frame against — mirroring CMD V2's own energyPowerHistoryParamsForPeriod():
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
import type { DateWindow } from "./types";

/** Map a period LABEL → the host date_window. `Today` keeps the detail-tab default {today, 2hour} (12 two-hour
 *  buckets); week/month roll up to a longer window with coarser sampling. Unknown labels default to Today. */
export function periodToDateWindow(period: string): DateWindow {
  const p = String(period ?? "").toLowerCase();
  if (p.includes("week")) return { range: "last-7-days", sampling: "day" };      // "This Week" / "Weekly"
  if (p.includes("month")) return { range: "this-month", sampling: "day" };      // "This Month" / "Monthly"
  if (p.includes("quarter")) return { range: "this-month", sampling: "week" };   // "Quarterly"
  if (p.includes("yester")) return { range: "yesterday", sampling: "2hour" };    // "Yesterday"
  return { range: "today", sampling: "2hour" };                                  // "Today" (default) + unknown
}
