import React from "react";
// Card 74 — Thermal Life (page transformer-asset-dashboard/thermal-life). ThermalLifeCard fed its OWN Layer-2 payload's
// `thermalLife` slice → the stress bar + winding/oil/loss metric strip.
//
// host-served is RETIRED → the payload IS the render source. ALWAYS-DRAWS [GOAL]: thermal stress / loss / load /
// efficiency fill REAL from the payload when present; the winding/oil temperature metric rows are domain readings that
// honest-blank ('—') when neuract has no column. A payload with no usable thermalLife slice renders the tab's OWN
// typed-empty view-model — the card STILL DRAWS its stress bar + metric strip structure, never a blank/null card and
// never a fabricated seed value (FillBar pcts finitized so a '—' never becomes a NaN width).
// ThermalLifeCard renders an instantaneous snapshot with NO date/range control — so it carries no onDateChange.
import { ThermalLifeCard } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/ThermalLifeCard";
import { thermalLifeVM } from "./view-model";

function ThermalLifeFill({ payload }: { payload: any }) {
  // thermalLifeVM NEVER returns null — always a drawable, fully-labelled slice (real live scalars from the payload, else
  // the tab's own empty-but-valid shape).
  return <ThermalLifeCard vm={thermalLifeVM(payload)} />;
}

export const card74 = (p: any): React.ReactNode => <ThermalLifeFill payload={p} />;
