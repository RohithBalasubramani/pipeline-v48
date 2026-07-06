import React from "react";
// Card 78 — Tap Position Optimization (page transformer-asset-dashboard/tap-rtcc, CMD V2 TapRtccTab). TapPositionCard
// fed its OWN Layer-2 payload's `tapPosition` slice (OLTC current/optimal position + RTCC mode gauge).
//
// ems_backend is RETIRED → the payload IS the render source. DOMAIN slot (OLTC tap position has no neuract column
// today) → HONEST-BLANK: when the payload carries no usable tapPosition slice, `tapPositionVM` yields the tab's OWN empty
// chrome (gauge at 0, KPI values '—', no insight) so the card STILL DRAWS its structure — never a blank/null card and
// never a fabricated/seed number (the seed gauge/KPI values are stripped server-side; a '—'/NaN can't reach the gauge
// geometry).
import { TapPositionCard } from "@cmd-v2/pages/assets/transformer/tabs/tap-rtcc/TapPositionCard";
import { tapPositionVM } from "./view-model";

function TapPositionFill({ payload }: { payload: any }) {
  // tapPositionVM NEVER returns null — always a drawable, fully-labelled slice (real gauge/KPIs from the payload, else
  // the tab's own empty-but-valid shape), with every gauge scalar finitized.
  return <TapPositionCard vm={tapPositionVM(payload)} />;
}

export const card78 = (p: any): React.ReactNode => <TapPositionFill payload={p} />;
