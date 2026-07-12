/**
 * SHARED (date-wiring concern) — panel-overview-harmonics-pq.
 *
 * The host-served date-window vocabulary, the strip's standalone filter
 * selection default, and the strip-control → host-served window mapping. Only
 * card 23 (PqTopStrip) owns a date control, so this is the one card that
 * imports selectionToWindow / defaultFilterSelection; DateWindow is shared by
 * the barrel's RenderFn signature.
 */
import {
  dateToIso,
  resolveEventFilter,
  type EventFilterSelection,
  type EventPreset,
  type ResampleMode,
} from "@cmd-v2/components/charts/primitives";

/* ── host-served date-window vocabulary ───────────────────────────────────
 * The host's onDateChange takes a DateWindow the host-served understands:
 *   range    ∈ today | yesterday | last-7-days | this-month | custom-range
 *   sampling ∈ hourly | 2hour | shift | day | week
 *   start/end — bare ISO dates, only when range is custom-range. */
export interface DateWindow {
  range: string;
  sampling: string;
  start?: string;
  end?: string;
}

/* Standalone filter selection (the strip's date controls). Identical to the
 * orchestrator's initial state + the story fixture. */
export function defaultFilterSelection(): EventFilterSelection {
  const today = dateToIso(new Date());
  return { preset: "today", resample: "hourly", customDate: today, rangeStart: today, rangeEnd: today };
}

/* ── strip-control value → host-served window mapping ─────────────────────
 * The strip emits a CMD V2 EventPreset + ResampleMode (resolved through
 * resolveEventFilter, the SAME resolver the orchestrator uses). We translate
 * the resolved selection into the host-served DateWindow vocabulary. Presets
 * the backend has no direct range word for (custom-date, last-month) collapse
 * to custom-range carrying the resolver's concrete start/end dates. */
const PRESET_TO_RANGE: Record<EventPreset, string> = {
  "today": "today",
  "yesterday": "yesterday",
  "last-7-days": "last-7-days",
  "this-month": "this-month",
  "custom-range": "custom-range",
  "custom-date": "custom-range",
  "last-month": "custom-range",
};

const RESAMPLE_TO_SAMPLING: Record<ResampleMode, string> = {
  "hourly": "hourly",
  "shift": "shift",
  "daily": "day",
  "weekly": "week",
  "monthly": "week",
};

/* Resolve a strip filter selection into the host-served window. We always
 * carry start/end (the resolver computes them for every preset); for the
 * collapsed presets that became custom-range, start/end ARE the window. */
export function selectionToWindow(selection: EventFilterSelection): DateWindow {
  const resolved = resolveEventFilter(selection);
  const range = PRESET_TO_RANGE[selection.preset] ?? "today";
  const sampling = RESAMPLE_TO_SAMPLING[resolved.resample] ?? "hourly";
  return {
    range,
    sampling,
    start: resolved.backendParams.start_date,
    end: resolved.backendParams.end_date,
  };
}
