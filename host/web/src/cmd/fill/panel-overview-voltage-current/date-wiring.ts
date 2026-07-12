// Card 18 date control → host-served window. The strip's filter row emits a
// CMD V2 {preset, resample, customDate, rangeStart, rangeEnd} selection. We
// run the page's OWN resolveEventFilter (which already resolves every preset
// — incl. last-month / custom-date — to concrete start/end + an allowed
// resample) and translate its backendParams into the host's date_window
// vocabulary (range ∈ today|yesterday|last-7-days|this-month|custom-range;
// sampling ∈ hourly|2hour|shift|day|week). Presets the host has no enum for
// (custom-date, last-month) collapse to a custom-range over the resolved span.

import { resolveEventFilter } from "@cmd-v2/components/charts/primitives";
import type {
  EventFilterSelection,
  EventPreset,
  ResampleMode,
} from "@cmd-v2/components/charts/primitives";

/** Host date_window — the shape onDateChange feeds back to the host re-fetch. */
export type { DateWindow } from "../../../types";   // ONE declaration (host/web/src/types.ts)
import type { DateWindow } from "../../../types";

/** CMD V2 EventPreset → host range. Presets the host doesn't model become a
 *  custom-range over the resolver's already-computed start/end span. */
const PRESET_TO_RANGE: Record<EventPreset, string> = {
  "today": "today",
  "yesterday": "yesterday",
  "last-7-days": "last-7-days",
  "this-month": "this-month",
  "custom-range": "custom-range",
  "custom-date": "custom-range",
  "last-month": "custom-range",
};

/** CMD V2 ResampleMode → host sampling. The host has no `month` bucket, so the
 *  monthly resample maps to its coarsest available bucket (`week`). */
const RESAMPLE_TO_SAMPLING: Record<ResampleMode, string> = {
  "hourly": "hourly",
  "shift": "shift",
  "daily": "day",
  "weekly": "week",
  "monthly": "week",
};

/** Resolve a CMD V2 strip selection into the host's host-served date_window.
 *  Always carries start/end (the resolver fills them for every preset), and
 *  sets range:'custom-range' whenever the preset has no host enum. */
export function selectionToWindow(selection: EventFilterSelection): DateWindow {
  const resolved = resolveEventFilter(selection);
  const range = PRESET_TO_RANGE[selection.preset] ?? "custom-range";
  return {
    range,
    sampling: RESAMPLE_TO_SAMPLING[resolved.resample] ?? "hourly",
    start: resolved.backendParams.start_date,
    end: resolved.backendParams.end_date,
  };
}

/** Preset change mirrors VoltageCurrentPanelTab: the multi-day presets force a
 *  daily resample, everything else falls back to hourly (the resolver then
 *  clamps to an allowed bucket). Keeps the emitted sampling self-consistent. */
export function resampleForPreset(preset: EventPreset): ResampleMode {
  return preset === "last-7-days" || preset === "this-month" || preset === "last-month"
    ? "daily"
    : "hourly";
}
