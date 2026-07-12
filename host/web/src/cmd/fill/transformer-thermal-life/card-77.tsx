import React from "react";
// Card 77 — Insulation Aging & Loss of Life (page transformer-asset-dashboard/thermal-life). InsulationAgingCard fed its
// OWN Layer-2 payload's `aging` slice → daily aging-factor (FAA) + cumulative loss-of-life.
//
// host-served is RETIRED → the payload IS the render source. ALWAYS-DRAWS [GOAL]: the daily aging-factor (FAA) +
// cumulative loss-of-life are purely insulation-DOMAIN metrics with NO neuract column today, so the payload carries no
// aging series — this card renders the tab's OWN typed-empty view-model (single '—' bucket → flat blank line, valid dual
// axes + legend + KPI scaffolding, all labels/colours). The chart STILL DRAWS its structure as an honest blank, never a
// blank/null card and never a fabricated seed. When neuract begins logging FAA/LOL the payload carries it and the same
// component plots it — no card change needed. Its header SamplingPicker (this-month × daily ↔ weekly) drives a per-card
// re-fetch via onDateChange.
import { InsulationAgingCard } from "@cmd-v2/pages/assets/transformer/tabs/thermal-life/InsulationAgingCard";
import { agingVM } from "./view-model";
import { reqToDateWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

function InsulationAgingFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  return (
    <InsulationAgingCard
      vm={agingVM(payload)}
      onRequest={(_chart, params) => onDateChange?.(reqToDateWindow(params))}
    />
  );
}

export const card77 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <InsulationAgingFill payload={p} onDateChange={od} />
);
