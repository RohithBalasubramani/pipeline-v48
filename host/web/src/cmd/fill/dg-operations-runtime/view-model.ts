// payload → ALWAYS-DRAWABLE view-model for the DG operations-runtime fill cards.
//
// Page: diesel-generator-asset-dashboard/operations-runtime. Only TWO cards fall here (FILL):
//   71 RuntimeDutyPanel     ← payload {duty}  (bar+line duty chart + KPI strip + per-run-event log)
//   73 PowerEnergyAnalysis  ← NO payload      (empty buckets + demand-limit nameplate line)
// Cards 70 (LiveOpsCard) + 72 (EnergyReliabilityCard) render DIRECTLY from their Layer-2 payload via COMPONENTS
// (Cmp70 / Cmp72) — they never reach FILL, so no code for them lives here.
//
// FRAMES=PAYLOADS [architecture]: ems_backend is RETIRED — the host emits `frames={}` EMPTY. So the ONLY data source is
// the Layer-2 `payload`; the old live-frame / energy-power column-row reducer / OpsFrame-from-frame machinery is DELETED.
//
// HONEST-DEGRADE contract [per card_handling]: the DG run-hours / duty history + per-run-event log are runtime-LOG data
// with NO neuract column and NO derived_metric, so Layer-2 carries no duty points / run rows for the general case — the
// cards draw CMD V2's OWN empty state (empty chart + "No runs in this period" / empty buckets), never a fabricated bar
// or seed number. Card 71 renders whatever `duty` slice Layer-2 DID emit (real or honest-blank '—') over that empty base.
import { buildOperationsRuntimeViewModel } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/viewModel";
import { DEFAULT_SAMPLING_SELECTION, DEMAND_LIMIT_KW, samplingToFilter } from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/config";
import type {
  DutyView,
  OpsFrame,
  OpsSnapshot,
  OpsViewModel,
  PowerEnergyView,
  RunsView,
} from "@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/types";

/** A ZERO-runtime `OpsSnapshot` — every runtime/reliability/energy field 0, status Idle. There is NO neuract source
 *  for this domain now (ems_backend retired), so the whole snapshot is the honest empty baseline. Passed through the
 *  DG tab's OWN `buildOperationsRuntimeViewModel` so the page draws its real chrome / labels / colours. */
function emptyOpsSnapshot(): OpsSnapshot {
  return {
    operatingState: "Idle",
    controlSwitch: "Off",
    breaker: "Open",
    loadPct: 0,
    runHoursLife: 0,
    runHoursService: 0,
    starts: 0,
    totalRuns: 0,
    availability: 0,
    mtbf: 0,
    mttr: 0,
    startupTime: 0,
    posKwh: 0,
    netKwh: 0,
    netKvarh: 0,
  };
}

/** CMD V2's OWN empty OpsViewModel — every slice at its typed-empty default (empty duty points, empty runs rows with
 *  real "All runs" header + column labels, empty power-energy buckets with the demand-limit line). The base every card
 *  fills its real Layer-2 slice over. NEVER null. */
function emptyVm(): OpsViewModel {
  const frame: OpsFrame = { snapshot: emptyOpsSnapshot(), buckets: [], count: 0, tickInterval: 0 };
  const { range, resample } = samplingToFilter(DEFAULT_SAMPLING_SELECTION);
  return buildOperationsRuntimeViewModel(frame, { range, resample, selectedBucket: null });
}

/** Card 71 — the `DutyView` for RuntimeDutyPanel's chart+KPI strip. Prefer the Layer-2 payload's `duty` slice (title /
 *  series / points / topKpis / tickInterval / demandLimitKw — real or honest-blank); a missing slice falls to CMD V2's
 *  OWN empty DutyView (empty points → the panel draws its empty-state chart chrome). NEVER null. */
export function dutyView(payload: any): DutyView {
  const d = payload && typeof payload === "object" ? payload.duty : undefined;
  return d && typeof d === "object" ? (d as DutyView) : emptyVm().duty;
}

/** Card 71 — the `RunsView` for RuntimeDutyPanel's per-run-event DataTable. The run log is a runtime-LOG with NO
 *  neuract source, so there are no run rows on the payload → CMD V2's OWN empty RunsView (empty rows → "No runs in this
 *  period" under the real "All runs" header + column labels). NEVER null, never a fabricated run row. */
export function runsView(): RunsView {
  return emptyVm().runs;
}

/** Card 73 — the `PowerEnergyView` (buckets + demand-limit line). The per-bucket demand/active/reactive series is
 *  DERIVED from the duty run-hours history, which has NO neuract source — so `buckets` is always empty (the panel draws
 *  its empty-state chrome) and `limitKw` is the DG demand-limit NAMEPLATE the axis needs to draw. Never a fabricated bar. */
export function powerEnergyView(): PowerEnergyView {
  return { buckets: [], limitKw: DEMAND_LIMIT_KW };
}
