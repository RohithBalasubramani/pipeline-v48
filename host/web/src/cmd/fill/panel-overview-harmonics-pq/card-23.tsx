/**
 * card 23 — PqTopStrip (issue summary strip).
 *
 * PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). The Layer-2
 * completed payload IS the render source: payload.strip = { pres, filterSelection,
 * timeChoice, timeOptions, stats, selectedTileKey }, carrying REAL neuract counts /
 * worst V-I or honest-blank per leaf. The old live snapshotFromFrame(frame) branch AND
 * the buildPQPeriods() fabrication fallback (synthetic iThd/vThd waves — a seed leak)
 * are DELETED. A payload that elides `stats` degrades to emptyStats() (zero counts +
 * blank worst — honest '—', NEVER a fabricated bucket).
 *
 * This is the ONE card on the page with a date/range/sampling control. Its preset /
 * resample / custom-date / range inputs drive a re-fetch of THIS card's payload via the
 * host onDateChange. The "at [time bucket]" picker (onTimeChange) is intra-window bucket
 * navigation, NOT a window change, so it is deliberately left as noop.
 */
import React from "react";

import { PqTopStrip } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import { buildHpqPresentation } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type { PQStats } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";
import {
  resolveEventFilter,
  type EventFilterSelection,
  type EventPreset,
  type ResampleMode,
} from "@cmd-v2/components/charts/primitives";

import { DateWindow, defaultFilterSelection, selectionToWindow } from "./date-window";
import { emptyStats } from "./derive";
import { noop } from "./noop";

function TopStripCard({
  payload,
  onDateChange,
}: {
  payload: any;
  onDateChange?: (dw: DateWindow) => void;
}): React.ReactElement | null {
  const args = payload?.strip ?? payload ?? {};
  let pres = args.pres ?? buildHpqPresentation().strip;

  // The strip owns its filter selection so the preset/resample/date inputs are
  // live, controlled inputs. Seed from the payload or today.
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

  // Stats / bucket labels come straight from the payload.
  let timeChoice: string = args.timeChoice ?? "";
  let timeOptions: string[] = args.timeOptions ?? [];
  let stats: PQStats = args.stats;

  // DRAW GUARANTEE — a payload that elided `stats` degrades to honest-empty (zero counts +
  // blank worst), NEVER a fabricated bucket. NEVER null.
  if (!stats) stats = emptyStats();

  // Per-leaf honest degrade: the executor scrubs seed clock labels to "" (a fixture "00:00" is not this run's
  // bucket). Blank entries are honest but unusable as selector rows — drop them and keep only the REAL labels.
  // Never re-fabricate fixture times here.
  timeOptions = timeOptions.filter((s: string) => typeof s === "string" && s.trim().length > 0);
  if (timeOptions.length === 0 && timeChoice) timeOptions = [timeChoice];

  // Elided-seed guard: Layer 2 elides `strip.segments` (a roster array) from the
  // fallback payload, but PqTopStrip does `pres.segments.map(...)` unconditionally
  // at render top. A present-but-partial `pres` (missing `segments`) would crash —
  // so ALWAYS-DRAW by falling back to CMD V2's OWN default strip presentation
  // (which carries a valid `segments` roster). NEVER null.
  if (!Array.isArray(pres?.segments)) {
    const def = buildHpqPresentation().strip;
    pres = { ...def, ...(pres ?? {}), segments: def.segments };
  }

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
  _frame?: any,
  onDateChange?: (dw: DateWindow) => void,
): React.ReactNode {
  return <TopStripCard payload={payload} onDateChange={onDateChange} />;
}
