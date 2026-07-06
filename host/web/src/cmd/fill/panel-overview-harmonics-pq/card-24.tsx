/**
 * card 24 — PqTimelineCard.
 *
 * PAYLOAD-DIRECT (ems_backend RETIRED — `frame` is always empty now). The Layer-2
 * completed payload IS the render source: payload.timeline = { pres, limits, periods,
 * selectedLabel, focus }, carrying REAL per-bucket periods or honest-blank. The old live
 * snapshotFromFrame(frame) branch AND the buildPQPeriods() fabrication fallback (synthetic
 * harmonic waves — a seed leak) are DELETED. PqTimelineCard does `periods.map(...)`, so an
 * empty `periods: []` renders an honest-empty timeline (chrome + no series), NEVER a mock.
 */
import React from "react";

import { PqTimelineCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import { buildHpqPresentation } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type {
  FocusKey,
  PQPeriod,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { lastPeriod } from "./derive";
import { noop } from "./noop";

export function renderTimeline(payload: any): React.ReactNode {
  const args = payload?.timeline ?? payload ?? {};
  const pres = args.pres ?? buildHpqPresentation().timeline;
  const limits = args.limits ?? buildHpqPresentation().limits;
  // periods straight from the payload; honest-empty [] when elided (PqTimelineCard .map()s it safely).
  const periods: PQPeriod[] = Array.isArray(args.periods) ? args.periods : [];
  const selectedLabel: string = args.selectedLabel ?? lastPeriod(periods)?.label ?? "";
  const focus: FocusKey | null = (args.focus as FocusKey) ?? null;

  return (
    <div className="h-full min-h-0">
      <PqTimelineCard
        pres={pres}
        limits={limits}
        periods={periods}
        selectedLabel={selectedLabel}
        focus={focus}
        onPeriodSelect={noop}
      />
    </div>
  );
}
