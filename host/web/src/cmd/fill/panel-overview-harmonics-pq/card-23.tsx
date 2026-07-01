/**
 * card 23 — PqTopStrip (issue summary strip).
 *
 * payload.strip = { pres, filterSelection, timeChoice, timeOptions, stats,
 * selectedTileKey }. Live: stats from the last period; timeOptions from the
 * live bucket labels.
 *
 * This is the ONE card on the page with a date/range/sampling control (the
 * EventStripControls "Show Issues for [preset] by [resample] …" row). Its
 * preset / resample / custom-date / range inputs drive a re-fetch of THIS
 * card's ems_backend frame via the host onDateChange. The "at [time bucket]"
 * picker (onTimeChange) is intra-window bucket navigation, NOT a window
 * change, so it is deliberately left as noop.
 */
import React from "react";

import { PqTopStrip } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import {
  buildHpqPresentation,
  buildPQPeriods,
  periodStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type {
  PQPeriod,
  PQStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";
import {
  resolveEventFilter,
  type EventFilterSelection,
  type EventPreset,
  type ResampleMode,
} from "@cmd-v2/components/charts/primitives";

import { DateWindow, defaultFilterSelection, selectionToWindow } from "./date-window";
import { lastPeriod, presentation } from "./derive";
import { noop } from "./noop";
import { snapshotFromFrame } from "./snapshot";

function TopStripCard({
  payload,
  frame,
  onDateChange,
}: {
  payload: any;
  frame?: any;
  onDateChange?: (dw: DateWindow) => void;
}): React.ReactElement | null {
  const args = payload?.strip ?? payload ?? {};
  const pres = args.pres ?? buildHpqPresentation().strip;

  // The strip owns its filter selection so the preset/resample/date inputs are
  // live, controlled inputs. Seed from the payload (story default) or today.
  const [filterSelection, setFilterSelection] = React.useState<EventFilterSelection>(
    args.filterSelection ?? defaultFilterSelection(),
  );

  // Apply one control patch, then re-fetch THIS card for the new window.
  const updateSelection = React.useCallback(
    (patch: Partial<EventFilterSelection>) => {
      setFilterSelection((prev: EventFilterSelection) => {
        const next = { ...prev, ...patch };
        try {
          onDateChange?.(selectionToWindow(next));
        } catch {
          /* host re-fetch is best-effort; never break the control */
        }
        return next;
      });
    },
    [onDateChange],
  );

  // Live stats / bucket labels (unchanged live mapper-fill).
  let timeChoice: string = args.timeChoice ?? "";
  let timeOptions: string[] = args.timeOptions ?? [];
  let stats: PQStats = args.stats;

  try {
    const snap = snapshotFromFrame(frame);
    if (snap) {
      const fullPres = presentation(snap);
      const selected = lastPeriod(snap.periods);
      if (selected) {
        timeOptions = snap.periods.map((p: PQPeriod) => p.label);
        timeChoice = selected.label;
        stats = periodStats(selected, fullPres.limits);
      }
    }
  } catch {
    /* keep payload defaults */
  }

  if (!stats) {
    const periods = buildPQPeriods();
    const sel = lastPeriod(periods)!;
    stats = periodStats(sel, buildHpqPresentation().limits);
    if (timeOptions.length === 0) timeOptions = periods.map((p: PQPeriod) => p.label);
    if (!timeChoice) timeChoice = sel.label;
  }

  // Elided-seed guard: Layer 2 elides `strip.segments` (a roster array) from the
  // fallback payload, but PqTopStrip does `pres.segments.map(...)` unconditionally
  // at render top. A present-but-partial `pres` (missing `segments`) crashes —
  // render null so the card shows a clean placeholder instead.
  if (!Array.isArray(pres?.segments)) return null;

  return (
    <PqTopStrip
      pres={pres}
      filterSelection={filterSelection}
      resolvedFilter={resolveEventFilter(filterSelection)}
      timeChoice={timeChoice}
      timeOptions={timeOptions}
      stats={stats}
      selectedTileKey={args.selectedTileKey || null}
      onTileSelect={noop}
      onPresetChange={(preset: EventPreset) =>
        updateSelection({
          preset,
          // mirror the orchestrator's resample default per preset
          resample:
            preset === "last-7-days" || preset === "this-month" || preset === "last-month"
              ? "daily"
              : "hourly",
        })
      }
      onResampleChange={(resample: ResampleMode) => updateSelection({ resample })}
      onTimeChange={noop}
      onCustomDateChange={(customDate: string) => updateSelection({ customDate })}
      onRangeStartChange={(rangeStart: string) => updateSelection({ rangeStart })}
      onRangeEndChange={(rangeEnd: string) => updateSelection({ rangeEnd })}
    />
  );
}

export function renderTopStrip(
  payload: any,
  frame?: any,
  onDateChange?: (dw: DateWindow) => void,
): React.ReactNode {
  return <TopStripCard payload={payload} frame={frame} onDateChange={onDateChange} />;
}
