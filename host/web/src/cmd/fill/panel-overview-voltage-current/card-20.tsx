import React from "react";
// Card 20 · Event Timeline — lt-pcc panel-overview Voltage&Current tab.
//
// PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). Priority:
// payload → CMD V2 HONEST-EMPTY view-model. EventTimelineChart maps/flatMaps `points`;
// if the payload elided the points leaf, fall back to the page's OWN honest-empty model
// (fallbackViewModel — empty points, chrome only, NO fabrication). NEVER null.
// The old live-aggregate-frame branch is dead code and was DELETED.

import { EventTimelineCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type { PeriodBucket } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";
import type { EventTimelinePoint } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventTimelineChart";

import {
  bundleFrom,
  fallbackViewModel,
  defaultPresentation,
} from "./view-model";

function TimelineCard({ trend }: { trend: any }) {
  // 1) payload (Layer-2 completed — real or honest-blank).
  let period: PeriodBucket = trend?.period;
  let points: EventTimelinePoint[] = trend?.points;
  let selectedLabel: string = trend?.selectedLabel;

  // 2) DRAW GUARANTEE — backfill points/period/label from the page's honest-empty model.
  if (!Array.isArray(points) || points.length === 0 || !period) {
    const b = bundleFrom(fallbackViewModel());
    points = (Array.isArray(points) && points.length > 0) ? points : b.points;
    period = period ?? b.period;
    selectedLabel = selectedLabel ?? b.label;
  }

  const pres = trend?.pres ?? defaultPresentation().timeline;
  return (
    <div className="h-full">
      <EventTimelineCard
        pres={pres}
        period={period}
        points={points}
        selectedLabel={selectedLabel}
        selectedTileKey={trend?.selectedTileKey ?? null}
        onPeriodSelect={() => undefined}
      />
    </div>
  );
}

export const card20 = (p: any): React.ReactNode =>
  <TimelineCard trend={p?.trend} />;
