import React from "react";
// Card 18 · Events strip — lt-pcc panel-overview Voltage&Current tab.
//
// PAYLOAD-DIRECT (ems_backend RETIRED — `frame` is always empty now). Priority:
// payload → CMD V2 HONEST-EMPTY view-model. The strip reads stats.worst*/counts + a filter
// selection; if the payload elided its leaves, fall back to the page's OWN honest-empty
// model / presentation (chrome only, NO fabrication) — never null. The old live-aggregate-
// frame branch is dead code and was DELETED. The date/range/sampling control stays LIVE:
// onPresetChange/onResampleChange/… emit onDateChange (a payload re-fetch, not a frame path).

import { EventsTopStrip } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventsTopStrip";
import { resolveEventFilter } from "@cmd-v2/components/charts/primitives";
import type {
  EventFilterSelection,
  EventPreset,
  ResampleMode,
} from "@cmd-v2/components/charts/primitives";
import type {
  PanelPeriodStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";

import { fallbackViewModel, defaultPresentation, bundleFrom } from "./view-model";
import { selectionToWindow, resampleForPreset, type DateWindow } from "./date-wiring";

/** A safe default CMD V2 filter selection when the payload elided strip.filterSelection. */
const DEFAULT_SELECTION: EventFilterSelection = {
  preset: "today",
  resample: "hourly",
  customDate: "",
  rangeStart: "",
  rangeEnd: "",
};

function StripCard({ strip, onDateChange }: { strip: any; onDateChange?: (dw: DateWindow) => void }) {
  // 1) payload (Layer-2 completed — real or honest-blank; data leaves may be elided).
  let stats: PanelPeriodStats | undefined = strip?.stats;
  let timeChoice: string | undefined = strip?.timeChoice;
  let timeOptions: string[] | undefined = strip?.timeOptions;

  // 2) DRAW GUARANTEE — backfill any missing leaf from the page's OWN honest-empty model.
  if (!stats || !timeChoice || !timeOptions || timeOptions.length === 0) {
    const b = bundleFrom(fallbackViewModel());
    stats = stats ?? b.stats;
    timeChoice = timeChoice ?? b.label;
    timeOptions = (timeOptions && timeOptions.length > 0) ? timeOptions : (b.timeOptions.length ? b.timeOptions : [b.label]);
  }

  const pres = strip?.pres ?? defaultPresentation().strip;

  // Local copy of the strip's CMD V2 filter selection (preset/resample/dates).
  const [selection, setSelection] = React.useState<EventFilterSelection>(strip?.filterSelection ?? DEFAULT_SELECTION);

  const applySelection = React.useCallback((next: EventFilterSelection) => {
    setSelection(next);
    onDateChange?.(selectionToWindow(next));
  }, [onDateChange]);

  const resolvedFilter = resolveEventFilter(selection);
  return (
    <EventsTopStrip
      pres={pres}
      preset={selection.preset}
      resample={resolvedFilter.resample}
      resolvedFilter={resolvedFilter}
      timeChoice={timeChoice}
      timeOptions={timeOptions}
      customDate={selection.customDate}
      rangeStart={selection.rangeStart}
      rangeEnd={selection.rangeEnd}
      stats={stats}
      selectedTileKey={strip?.selectedTileKey ?? null}
      onTileSelect={() => undefined}
      onPresetChange={(preset: EventPreset) => applySelection({ ...selection, preset, resample: resampleForPreset(preset) })}
      onResampleChange={(resample: ResampleMode) => applySelection({ ...selection, resample })}
      onTimeChange={() => undefined}
      onCustomDateChange={(customDate: string) => applySelection({ ...selection, customDate })}
      onRangeStartChange={(rangeStart: string) => applySelection({ ...selection, rangeStart })}
      onRangeEndChange={(rangeEnd: string) => applySelection({ ...selection, rangeEnd })}
    />
  );
}

export const card18 = (p: any, _f?: any, onDateChange?: (dw: any) => void): React.ReactNode =>
  <StripCard strip={p?.strip} onDateChange={onDateChange} />;
