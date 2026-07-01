import React from "react";
// Card 47 — PowerQualityCard: a now-snapshot KPI card (takes only `snapshot`, no SamplingPicker). Live-only; no date
// control to wire, so onDateChange is ignored here.
import { PowerQualityCard } from "@cmd-v2/pages/electrical/tabs/power-quality/PowerQualityCard";
import type { PowerQualitySnapshot } from "@cmd-v2/pages/electrical/tabs/power-quality/types";
import { liveSnapshot } from "./mappers";

/** Card 47 — PowerQualityCard. payload = { snapshot } (story args). Live: map a summary frame to a snapshot; else
 *  render the payload's byte-identical default snapshot. */
function PowerQualityCardFill({ payload, frame }: { payload: any; frame?: any }) {
  let snapshot: PowerQualitySnapshot = payload?.snapshot;
  try {
    const live = liveSnapshot(frame);
    if (live) snapshot = live;
  } catch {
    /* keep payload default */
  }
  if (!snapshot) return null;
  return <PowerQualityCard snapshot={snapshot} className="h-full w-full" />;
}

export const card47 = (p: any, f?: any) => <PowerQualityCardFill payload={p} frame={f} />;
