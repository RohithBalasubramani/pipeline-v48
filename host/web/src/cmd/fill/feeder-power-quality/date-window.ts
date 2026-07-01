/* ── Per-card date control → ems_backend window ───────────────────────────
 * The two rail charts (48/49) carry a real CMD V2 <SamplingPicker> via their
 * `onSamplingChange?: (next: SamplingSelection) => void` prop. SamplingSelection
 * = { preset: PresetId, range: DateRange | null, resolution?, shift? } (Apply-only).
 * We translate that committed selection into the host's ems_backend date_window
 * vocabulary — range ∈ today|yesterday|last-7-days|this-month|custom-range,
 * sampling ∈ hourly|2hour|shift|day|week — and hand it to onDateChange so the host
 * re-fetches JUST this card's frame for the new window. This mirrors the real tab's
 * powerQualitySamplingToHistoryRequest (preset → range, resolution → sampling), but
 * emits the host vocabulary (custom-range + start/end) rather than the legacy backend
 * range keys. */
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";

export type DateWindow = { range?: string; start?: string; end?: string; sampling?: string };

// SamplingSelection.preset → ems_backend range. PresetId 'last-month' has no host
// equivalent; fold it onto 'this-month' to stay in-vocabulary. 'custom' is handled
// separately (→ 'custom-range' + start/end from the resolved DateRange).
const PRESET_TO_RANGE: Record<string, string> = {
  today: "today",
  yesterday: "yesterday",
  "last-7-days": "last-7-days",
  "this-month": "this-month",
  "last-month": "this-month",
};

/** Map a committed CMD V2 SamplingSelection → the host's ems_backend date_window. */
export function samplingToDateWindow(sel: SamplingSelection): DateWindow {
  // resolution ∈ 2hour|shift|day|week|hourly — already in the sampling vocabulary.
  const sampling = (sel.resolution as string | undefined) ?? "2hour";
  if (sel.preset === "custom") {
    return {
      range: "custom-range",
      start: sel.range?.start ?? undefined,
      end: sel.range?.end ?? undefined,
      sampling,
    };
  }
  return { range: PRESET_TO_RANGE[sel.preset] ?? "today", sampling };
}
