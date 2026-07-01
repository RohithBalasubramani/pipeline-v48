/**
 * SHARED (view-model derivation concern) — panel-overview-harmonics-pq.
 *
 * The small derivations every card shares off a mapped snapshot: the
 * presentation (`pres`) preference rule, the orchestrator's table-period rule,
 * and the last-period selector.
 */
import { buildHpqPresentation } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type { PanelHarmonicsPqSnapshot } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/mockSource";
import type {
  HpqPresentation,
  PQPeriod,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

/* The presentation (`pres`) the card reads, preferring the payload's morphed
 * value (exact_metadata) and falling back to the default producer. */
export function presentation(snap: PanelHarmonicsPqSnapshot | null): HpqPresentation {
  return snap?.presentation ?? buildHpqPresentation();
}

/* The orchestrator's table-period rule: priorityRows (current ranking) become
 * the table's rows when present, else the selected/last period. */
export function liveTablePeriod(snap: PanelHarmonicsPqSnapshot, selected: PQPeriod): PQPeriod {
  const priorityRows = snap.apiExtras?.priorityRows;
  if (priorityRows && priorityRows.length > 0) {
    return {
      label: snap.apiExtras?.selectedBucketLabel ?? selected.label,
      panels: priorityRows,
    };
  }
  return selected;
}

export const lastPeriod = (periods: PQPeriod[]): PQPeriod | undefined =>
  periods[periods.length - 1];
