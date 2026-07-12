// date control wiring (HistoryPanel SamplingPicker → host window) — the ONE implementation of the
// SamplingSelection family. Previously byte-identical copies in feeder-voltage-current/ and
// diesel-generator-voltage-current/ (they differed only in comment wording). Folders with genuinely
// divergent token maps (transformer-tap-rtcc rangeToHost, dg-operations-runtime resolutionToSampling,
// harmonics-pq's EventFilterSelection path) keep their own translators.
//
// HistoryPanel renders a real CMD V2 `SamplingPicker` (header) ONLY when its payload carries BOTH
// `data.sampling` (the committed SamplingSelection) and `data.onSamplingChange`. The picker's `onChange`
// fires on Apply with a `SamplingSelection` { preset, range:{start,end}|null, resolution?, shift? }.
// We translate that → the host date_window vocabulary and hand it to the host's onDateChange, which
// re-runs JUST this card for the new window (frames are retired, so the host re-derives the card's
// payload — no host-served re-fetch). The page's own hook
// (useVoltageCurrentData.voltageCurrentHistorySelectionToParams) is the reference for the
// preset→sampling pairing; the host range tokens are the PresetId form
// (today | yesterday | last-7-days | this-month | custom-range).
import {
  presetRange,
  type DateRange,
  type PresetId,
  type SamplingSelection,
} from "@cmd-v2/components/charts/primitives";
import type { HistoryPanelData } from "@cmd-v2/pages/electrical/tabs/voltage-current/types";
import type { DateWindow, OnDateChange } from "../../../types";

/** Default committed selection so the picker renders (Today, records the seed
 *  resolution the card's history grid uses — `2hour`, matching the other detail
 *  tabs' today grid). */
export function defaultSampling(): SamplingSelection {
  return { preset: "today", range: presetRange("today", new Date()), resolution: "2hour" };
}

/** Map a committed `SamplingSelection` → the host date_window. range tokens stay
 *  in the host PresetId vocabulary; presets with no host range token (last-month)
 *  fall to an explicit custom-range window from the resolved dates. The chosen
 *  resolution (already one of 2hour|shift|day|week from the picker) rides through
 *  as `sampling`; presets seed a sane default sampling when none is committed. */
export function samplingToWindow(sel: SamplingSelection): DateWindow {
  const range: DateRange | null = sel.range ?? null;
  // resolution the operator picked (if any) wins; otherwise the preset default.
  const chosen = sel.resolution; // 2hour | shift | day | week, or undefined
  const custom = (sampling: string): DateWindow => ({
    range: "custom-range",
    sampling: chosen ?? sampling,
    start: range?.start ?? undefined,
    end: range?.end ?? undefined,
  });
  switch (sel.preset as PresetId) {
    case "yesterday":
      return { range: "yesterday", sampling: chosen ?? "hourly" };
    case "last-7-days":
      return { range: "last-7-days", sampling: chosen ?? "day" };
    case "this-month":
      return { range: "this-month", sampling: chosen ?? "week" };
    case "last-month":
      // No host range token for last-month → explicit [start,end] window.
      return custom("week");
    case "custom":
      return custom("hourly");
    case "today":
    default:
      return { range: "today", sampling: chosen ?? "2hour" };
  }
}

/** Overlay the SamplingPicker control onto a card's resolved `HistoryPanelData`
 *  so the picker renders AND its Apply drives the host re-fetch. No-op (returns
 *  data unchanged) when the host gives no onDateChange (older call path). */
export function withDateControl(
  data: HistoryPanelData,
  onDateChange?: OnDateChange,
): HistoryPanelData {
  if (!onDateChange) return data;
  // Keep any picker config the payload already set; only ensure a committed
  // `sampling` + the change handler exist (HistoryPanel gates the picker on both).
  return {
    ...data,
    sampling: data.sampling ?? defaultSampling(),
    onSamplingChange: (next: SamplingSelection) => onDateChange(samplingToWindow(next)),
  };
}
