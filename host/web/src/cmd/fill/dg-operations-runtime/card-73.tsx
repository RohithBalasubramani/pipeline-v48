import React from "react";
// Card 73 — Power Energy Analysis (page diesel-generator-asset-dashboard/operations-runtime).
// PowerEnergyAnalysisPanel (shared primitive: per-bucket demand/active/reactive bars + demand-limit line +
// SegmentedControl + SamplingPicker) rendered from metadata only.
//
// NO STORYBOOK STORY [noted]: card 73 has no harvested story_id in card_payloads — there is no seed payload to open.
// So this card is rendered ENTIRELY from metadata + honest-empty: the demand-limit reference line is a frontend
// nameplate const (DEMAND_LIMIT_KW) the panel needs to draw its axis, and `buckets` is EMPTY.
//
// FRAMES=PAYLOADS [architecture]: ems_backend is RETIRED (frames={} EMPTY), so there is no live-frame path anyway. The
// per-bucket demand_present_kw / active_energy / reactive_energy time-series is DERIVED from the DG duty run-hours
// history, which has NO neuract source — so `buckets` is always empty and the panel draws its own empty-state chrome
// (axes + legend + SamplingPicker, no bars) — never a fabricated bar or seed number.
// This card owns a SamplingPicker + a bucket drilldown, so it holds local sampling + selection state. With ems_backend
// retired the onDateChange re-fetch is a no-op, but the control is real CMD V2 chrome and still renders.
import { PowerEnergyAnalysisPanel } from "@cmd-v2/components/charts/primitives";
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";
import { DEFAULT_SAMPLING_SELECTION } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/config";
import { powerEnergyView } from "./view-model";
import { samplingToWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

function PowerEnergyAnalysisFill({ payload: _payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  const [sampling, setSampling] = React.useState<SamplingSelection>(DEFAULT_SAMPLING_SELECTION);
  const [selIdx, setSelIdx] = React.useState<number | null>(null);
  // powerEnergyView is metadata-only: `buckets` empty (the panel draws its empty-state chrome) + `limitKw` the
  // nameplate demand-limit line the axis needs. selIdx is guarded to null since there are no buckets to select.
  const { buckets, limitKw } = powerEnergyView();
  const safeSelIdx = buckets.length > 0 ? selIdx : null;
  return (
    <PowerEnergyAnalysisPanel
      buckets={buckets}
      selIdx={safeSelIdx}
      limitKw={limitKw}
      sampling={sampling}
      onSamplingChange={(next) => {
        setSampling(next);
        setSelIdx(null);
        onDateChange?.(samplingToWindow(next));
      }}
    />
  );
}

export const card73 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <PowerEnergyAnalysisFill payload={p} onDateChange={od} />
);
