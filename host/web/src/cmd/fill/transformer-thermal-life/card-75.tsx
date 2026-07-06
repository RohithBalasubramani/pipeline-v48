import React from "react";
// Card 75 — Life & Capacity (page transformer-asset-dashboard/thermal-life). LifeCapacityCard fed its OWN Layer-2
// payload's `lifeCapacity` slice → the life-remaining + derating FillBar groups.
//
// ems_backend is RETIRED → the payload IS the render source. ALWAYS-DRAWS [GOAL]: the derating bar (load kVA / derated
// kVA / headroom) is electrical-derivable and fills REAL from the payload; the life-remaining bar (years / aging) is an
// insulation-life domain reading that reads 0/empty when neuract has no column. A payload with no usable lifeCapacity
// slice renders the tab's OWN typed-empty view-model — the card STILL DRAWS both bar groups, never a blank/null card and
// never a fabricated seed. EVERY scalar is finitized (`lifeRemainingYears.toFixed(1)` would throw on a null/'—').
// LifeCapacityCard renders an instantaneous snapshot with NO date/range control — so it carries no onDateChange.
import { LifeCapacityCard } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/LifeCapacityCard";
import { lifeCapacityVM } from "./view-model";

function LifeCapacityFill({ payload }: { payload: any }) {
  // lifeCapacityVM NEVER returns null — always a drawable, fully-labelled slice with every FillBar/toFixed scalar finite.
  return <LifeCapacityCard vm={lifeCapacityVM(payload)} />;
}

export const card75 = (p: any): React.ReactNode => <LifeCapacityFill payload={p} />;
