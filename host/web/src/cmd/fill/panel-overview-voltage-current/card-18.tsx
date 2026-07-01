import React from "react";
// Card 18 · Events strip — lt-pcc panel-overview Voltage&Current tab.

import { EventsTopStrip } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventsTopStrip";
import { resolveEventFilter } from "@cmd-v2/components/charts/primitives";
import type {
  EventFilterSelection,
  EventPreset,
  ResampleMode,
} from "@cmd-v2/components/charts/primitives";
import type {
  PanelPeriodStats,
  PeriodBucket,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";

import { panelVcViewModel, selectPeriod, statsFor } from "./view-model";
import { selectionToWindow, resampleForPreset, type DateWindow } from "./date-wiring";

function StripCard({ strip, frame, onDateChange }: { strip: any; frame?: any; onDateChange?: (dw: DateWindow) => void }) {
  // Seed (byte-identical default) data.
  let stats: PanelPeriodStats = strip.stats;
  let timeChoice: string = strip.timeChoice;
  let timeOptions: string[] = strip.timeOptions;
  try {
    const data = panelVcViewModel(frame);
    if (data) {
      const { period, label } = selectPeriod(data);
      stats = statsFor(data, period, label);
      timeChoice = label;
      timeOptions = data.periods.length ? data.periods.map((p: PeriodBucket) => p.label) : [label];
    }
  } catch { /* keep seed */ }

  // Local copy of the strip's CMD V2 filter selection (preset/resample/dates).
  // The control row drives THIS state; each change maps to a host date_window
  // and re-fetches just this card's frame via onDateChange. The view-model
  // mapper-fill above is unchanged — only the control wiring is added.
  const [selection, setSelection] = React.useState<EventFilterSelection>(strip.filterSelection);

  // Push a selection into local state AND the host window re-fetch (optional-call
  // guarded — older call paths pass no onDateChange).
  const applySelection = React.useCallback((next: EventFilterSelection) => {
    setSelection(next);
    onDateChange?.(selectionToWindow(next));
  }, [onDateChange]);

  const resolvedFilter = resolveEventFilter(selection);
  return (
    <EventsTopStrip
      pres={strip.pres}
      preset={selection.preset}
      resample={resolvedFilter.resample}
      resolvedFilter={resolvedFilter}
      timeChoice={timeChoice}
      timeOptions={timeOptions}
      customDate={selection.customDate}
      rangeStart={selection.rangeStart}
      rangeEnd={selection.rangeEnd}
      stats={stats}
      selectedTileKey={strip.selectedTileKey ?? null}
      onTileSelect={() => undefined}
      // Period preset: mirror the live tab — picking a multi-day preset forces a
      // daily resample, others reset to hourly; resolveEventFilter then clamps.
      onPresetChange={(preset: EventPreset) => applySelection({ ...selection, preset, resample: resampleForPreset(preset) })}
      onResampleChange={(resample: ResampleMode) => applySelection({ ...selection, resample })}
      // The hour-bucket picker selects WITHIN the current window (a bucket label,
      // not a date) — it's not a window re-fetch, so leave it inert.
      onTimeChange={() => undefined}
      onCustomDateChange={(customDate: string) => applySelection({ ...selection, customDate })}
      onRangeStartChange={(rangeStart: string) => applySelection({ ...selection, rangeStart })}
      onRangeEndChange={(rangeEnd: string) => applySelection({ ...selection, rangeEnd })}
    />
  );
}

export const card18 = (p: any, f?: any, onDateChange?: (dw: any) => void): React.ReactNode =>
  p?.strip ? <StripCard strip={p.strip} frame={f} onDateChange={onDateChange} /> : null;
