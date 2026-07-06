// SamplingPicker (RuntimeDutyPanel card 71 header · PowerEnergyAnalysisPanel card 73 header)
// → host date_window wiring for the DG operations-runtime fill cards.
//
// RuntimeDutyPanel + PowerEnergyAnalysisPanel each render a real CMD V2 `SamplingPicker`
// whose `onChange` fires on Apply with a committed `SamplingSelection`
// { preset, range:{start,end}|null, resolution?, shift? }. Cards 71/73 translate that → the
// host date_window vocabulary via `samplingToWindow` and hand it to the host onDateChange.
// (ems_backend is RETIRED so the host re-fetch is now a no-op, but the picker is real CMD V2
// chrome and the committed window is still surfaced.) Mirrors the DG tab's OWN
// config.samplingToFilter() preset→resample pairing:
//   range      ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling   ∈ hourly | 2hour | shift | day | week
// The DG resolution vocab is hourly | daily | shift → mapped onto the host sampling tokens.
import type { DateWindow } from "./types";

// The DG tab's SamplingPicker uses PresetId tokens directly, so `preset` already matches the
// host range vocabulary except `last-month` (no host range token) and `custom` (needs [start,end]).
type Sel = {
  preset?: string;
  range?: { start?: string; end?: string } | null;
  resolution?: string;
  shift?: string;
};

/** DG resolution (hourly|daily|shift) → host sampling token, or the preset default when unset.
 *  daily → day; shift stays shift; hourly stays hourly. */
function resolutionToSampling(resolution: string | undefined, presetDefault: string): string {
  if (resolution === "daily") return "day";
  if (resolution === "shift") return "shift";
  if (resolution === "hourly") return "hourly";
  return presetDefault;
}

/** Map a committed `SamplingSelection` → the host date_window. Presets carry a sane default
 *  sampling; the operator-chosen resolution (if any) overrides it. `last-month` has no host
 *  range token → an explicit custom-range [start,end]; `custom` rides the resolved dates. */
export function samplingToWindow(sel: Sel): DateWindow {
  const range = sel?.range ?? null;
  const start = range?.start ?? undefined;
  const end = range?.end ?? undefined;
  switch (sel?.preset) {
    case "yesterday":
      return { range: "yesterday", sampling: resolutionToSampling(sel.resolution, "2hour") };
    case "last-7-days":
      return { range: "last-7-days", sampling: resolutionToSampling(sel.resolution, "day") };
    case "this-month":
      return { range: "this-month", sampling: resolutionToSampling(sel.resolution, "day") };
    case "last-month":
      return { range: "custom-range", sampling: resolutionToSampling(sel.resolution, "week"), start, end };
    case "custom":
      return { range: "custom-range", sampling: resolutionToSampling(sel.resolution, "hourly"), start, end };
    case "today":
    default:
      return { range: "today", sampling: resolutionToSampling(sel.resolution, "hourly") };
  }
}
