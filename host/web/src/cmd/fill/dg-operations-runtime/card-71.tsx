import React from "react";
// Card 71 — Runtime & Duty (page diesel-generator-asset-dashboard/operations-runtime).
// RuntimeDutyPanel (bar+line duty chart + KPI strip + per-run-event DataTable) rendered from the Layer-2 payload {duty}.
//
// FRAMES=PAYLOADS [architecture]: host-served is RETIRED (frames={} EMPTY), so there is no live-frame / mapper path.
// RuntimeDutyPanel reads `duty` (DutyView — title/series/points/topKpis, carried on the Layer-2 payload, real or
// honest-blank '—') AND `runs` (RunsView — the per-run-event log). The DG run-hours bars + run-event rows are
// runtime-LOG data with NO neuract column, so Layer-2 carries no run rows → `runs` is CMD V2's OWN empty RunsView
// ("No runs in this period" under the real "All runs" header). The panel ALWAYS DRAWS its real chrome (chart frame +
// axes, KPI strip, runs-table headers) — never fabricated bars / run rows, never a blank/null card, never a seed.
//
// This card OWNS the page time/sampling control (SamplingPicker in the header) + the bucket-click filter, so it holds
// local `sampling` + `selectedBucket` state and wires Apply → the host per-card re-fetch (onDateChange). With
// host-served retired the re-fetch is a no-op, but the control is real CMD V2 chrome and still renders.
import { RuntimeDutyPanel } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/RuntimeDutyPanel";
import { DEFAULT_SAMPLING_SELECTION } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/config";
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";
import { dutyView, runsView } from "./view-model";
import { samplingToWindow } from "./date-wiring";
import type { OnDateChange } from "./types";

function RuntimeDutyFill({ payload, onDateChange }: { payload: any; onDateChange?: OnDateChange }) {
  const [sampling, setSampling] = React.useState<SamplingSelection>(DEFAULT_SAMPLING_SELECTION);
  const [selectedBucket, setSelectedBucket] = React.useState<number | null>(null);
  // dutyView is the Layer-2 duty slice (or CMD V2's empty DutyView); runsView is CMD V2's OWN empty RunsView
  // (the run log has no neuract source). Both never null → the panel draws its chrome, never a blank/null card.
  const duty = dutyView(payload);
  const runs = runsView();
  // Guard the bucket selection to null when the duty chart has no buckets (nothing selectable → no NaN drilldown).
  const safeBucket = Array.isArray(duty.points) && duty.points.length > 0 ? selectedBucket : null;
  return (
    <RuntimeDutyPanel
      duty={duty}
      runs={runs}
      selectedBucket={safeBucket}
      onSelectBucket={setSelectedBucket}
      sampling={sampling}
      onSamplingChange={(next) => {
        setSampling(next);
        onDateChange?.(samplingToWindow(next));
      }}
    />
  );
}

export const card71 = (p: any, _f?: any, od?: OnDateChange): React.ReactNode => (
  <RuntimeDutyFill payload={p} onDateChange={od} />
);
