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
import { withSectionSplit } from "../../section-split";

// sections-aware switch [sections overlay]: a bus-section compare payload carries pres.sectionSplit + per-section
// series keys (sag_a/sag_b …) the ORIGINAL card's closed accessor record cannot map (`value: undefined` → chart
// throw). The wrapper renders the SAME CMD_V2 chart primitive with key-generic accessors; without the marker the
// original component renders byte-identically.
const Timeline0 = withSectionSplit(EventTimelineCard);

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
      <Timeline0
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
