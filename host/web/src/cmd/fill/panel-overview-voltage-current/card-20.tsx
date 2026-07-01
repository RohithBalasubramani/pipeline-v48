import React from "react";
// Card 20 · Event Timeline — lt-pcc panel-overview Voltage&Current tab.

import { EventTimelineCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type { PeriodBucket } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";
import type { EventTimelinePoint } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventTimelineChart";

import { panelVcViewModel, selectPeriod } from "./view-model";

function TimelineCard({ trend, frame }: { trend: any; frame?: any }) {
  let period: PeriodBucket = trend.period;
  let points: EventTimelinePoint[] = trend.points;
  let selectedLabel: string = trend.selectedLabel;
  try {
    const data = panelVcViewModel(frame);
    if (data) {
      const sel = selectPeriod(data);
      period = sel.period;
      points = data.timelinePoints;
      selectedLabel = sel.label;
    }
  } catch { /* keep seed */ }
  // GUARD: EventTimelineChart maps/flatMaps `points` (points.map, points.flatMap) throughout; Layer 2 elides the points
  // leaf from the seed payload, so render a placeholder instead of crashing on `.map` of undefined.
  if (!Array.isArray(points) || points.length === 0) return null;
  return (
    <div className="h-full">
      <EventTimelineCard
        pres={trend.pres}
        period={period}
        points={points}
        selectedLabel={selectedLabel}
        selectedTileKey={trend.selectedTileKey ?? null}
        onPeriodSelect={() => undefined}
      />
    </div>
  );
}

export const card20 = (p: any, f?: any): React.ReactNode =>
  p?.trend ? <TimelineCard trend={p.trend} frame={f} /> : null;
