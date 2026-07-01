import React from "react";
// Card 45 — Current Health Summary (page individual-feeder-meter-shell/voltage-current, CMD V2
// Equipment-Detail "Voltage & Current" tab). HealthSummaryPanel fed the LIVE `voltage-current`
// column-row ems_backend frame (current slice), mapped through the page's OWN reducers + mapper +
// view-model. Honest-degrade: a missing/unmappable frame renders the byte-faithful payload default.
// Card 45 renders a live health snapshot with NO date/range/sampling control — so it carries no onDateChange.
import { HealthSummaryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { liveHealth } from "./frame-view-model";
import { healthData, healthPhaseVariant } from "./payload-unwrap";

/** Card 45 — Current Health Summary: HealthSummaryPanel fed the live
 *  `voltage-current` column-row frame (current slice). */
function CurrentHealthCard({ payload, frame }: { payload: any; frame?: any }) {
  const fallback = healthData(payload);
  const live = liveHealth(frame, "current");
  const data = live ?? fallback;
  // GUARD: HealthSummaryPanel maps data.metrics (MetricStrip) and data.phases (PhaseRows/PhaseBarRows); Layer 2 elides
  // those array leaves from the seed payload, so render a placeholder instead of crashing on `.map` of undefined.
  if (!data || !Array.isArray(data.metrics) || !Array.isArray(data.phases)) return null;
  return <HealthSummaryPanel data={data} phaseVariant={healthPhaseVariant(payload)} />;
}

export const card45 = (p: any, f?: any): React.ReactNode => (
  <CurrentHealthCard payload={p} frame={f} />
);
