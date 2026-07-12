// payload unwrap (story args → component props) for the diesel-generator voltage-current fill cards.
//
// The DG V&C story args are the shared-electrical slices (the DG viewModel emits the shared
// `VoltageCurrentViewModel`, so its 4 slices are byte-shaped as HealthCardData / HistoryPanelData):
//   VoltageHealth / CurrentHealth story → args { variant, data: HealthCardData }
//   VoltageHistory / CurrentHistory story → args { variant, data: HistoryPanelData }
// The DG story renders the health cards with `phaseVariant="bars"` (11 kV L-L genset labels), NOT
// the single-char "rows" variant the LT-PCC screens use.
import { type PhaseVariant } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import type {
  HealthCardData,
  HistoryPanelData,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

// History story render: <HistoryPanel data={history.data} />
export function historyData(payload: any): HistoryPanelData | undefined {
  return payload?.data;
}
// Health story render: <HealthSummaryPanel data={health.data} phaseVariant="bars" />
export function healthData(payload: any): HealthCardData | undefined {
  return payload?.data;
}
/** DG genset terminal renders multi-char L-L / R-Y-B-N labels → the `bars` variant (the DG story's
 *  hard-coded `phaseVariant="bars"`); honour a payload override if Layer 2 ever emits one. */
export function healthPhaseVariant(payload: any): PhaseVariant {
  return (payload?.phaseVariant as PhaseVariant) ?? "bars";
}

/* ── sanitize — the ONE shared implementation (../shared/vc-sanitize, F4 2026-07-12). The DG folder's old local
 * copy zeroed expectedMin/Max unconditionally (a degenerate 0-band when showExpectedRange came true) and did not
 * object-filter rows — the shared feeder-strict version hides a non-finite band instead and filters non-objects;
 * client-gate verified over saved DG responses (identical clean/throw/NaN counts). */
export { sanitizeHistory, sanitizeHealth } from "../shared/vc-sanitize";
