/**
 * card 24 — PqTimelineCard.
 *
 * payload.timeline = { pres, limits, periods, selectedLabel, focus }. Live:
 * the per-bucket periods from the mapped snapshot.
 */
import React from "react";

import { PqTimelineCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import {
  buildHpqPresentation,
  buildPQPeriods,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type {
  FocusKey,
  PQPeriod,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { lastPeriod, presentation } from "./derive";
import { noop } from "./noop";
import { snapshotFromFrame } from "./snapshot";

export function renderTimeline(payload: any, frame?: any): React.ReactNode {
  const args = payload?.timeline ?? payload ?? {};
  const pres = args.pres ?? buildHpqPresentation().timeline;
  let limits = args.limits ?? buildHpqPresentation().limits;
  let periods: PQPeriod[] = args.periods ?? [];
  let selectedLabel: string = args.selectedLabel ?? "";
  const focus: FocusKey | null = (args.focus as FocusKey) ?? null;

  try {
    const snap = snapshotFromFrame(frame);
    if (snap) {
      const fullPres = presentation(snap);
      limits = fullPres.limits;
      periods = snap.periods;
      selectedLabel = lastPeriod(periods)?.label ?? selectedLabel;
    }
  } catch {
    /* keep payload defaults */
  }

  if (periods.length === 0) {
    periods = buildPQPeriods();
    if (!selectedLabel) selectedLabel = lastPeriod(periods)?.label ?? "";
  }

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
