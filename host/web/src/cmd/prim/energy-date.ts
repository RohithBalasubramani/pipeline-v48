// prim/energy-date.ts — period/sampling → host date_window for the energy family cards. [primitives-only port]
//
// Not a family file (a .ts, so prim/index.ts's `./*.tsx` glob never treats it as a CARDS module). Mirrors the retired
// fill's feeder-energy-power/date-wiring.ts + energy-power/config range mapping: a TodaysEnergyCard / PeriodSelect
// period LABEL, or a SamplingPicker committed selection, becomes the host window vocabulary the host re-fetches this
// card's frame against (range ∈ today|yesterday|last-7-days|this-month|custom-range; sampling ∈ hourly|2hour|shift|day|week).
export type { DateWindow } from "../../types";
import type { DateWindow } from "../../types";
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";

/** TodaysEnergyCard / PeriodSelect period LABEL → host window (feeder cards 39/42). */
export function periodToWindow(period: string): DateWindow {
  const p = String(period ?? "").toLowerCase();
  if (p.includes("week")) return { range: "last-7-days", sampling: "day" };     // "This Week" / "Weekly"
  if (p.includes("month")) return { range: "this-month", sampling: "day" };     // "This Month" / "Monthly"
  if (p.includes("quarter")) return { range: "this-month", sampling: "week" };  // "Quarterly"
  if (p.includes("yester")) return { range: "yesterday", sampling: "2hour" };   // "Yesterday"
  return { range: "today", sampling: "2hour" };                                 // "Today" (default) + unknown
}

const PRESET_TO_RANGE: Record<string, string> = {
  "today": "today",
  "yesterday": "yesterday",
  "last-7-days": "last-7-days",
  "this-week": "last-7-days",
  "last-24h": "today",
  "this-month": "this-month",
  "last-month": "custom-range",
  "custom": "custom-range",
};

/** SamplingPicker committed selection → host window (cards 40/16/17). Custom / last-month carry the resolved span. */
export function samplingToWindow(sel: SamplingSelection): DateWindow {
  const preset = String(sel?.preset ?? "today");
  const range = PRESET_TO_RANGE[preset] ?? "custom-range";
  const multiDay = preset !== "today" && preset !== "yesterday";
  const sampling = sel?.resolution === "by-shift" ? "shift" : multiDay ? "day" : "2hour";
  return { range, sampling, start: sel?.range?.start ?? null, end: sel?.range?.end ?? null };
}
