// payload → props (story args → component props) for the feeder voltage-current fill cards.
//
// FRAMES ARE RETIRED. The host emits `frames={}`; the ONLY data source is the Layer-2 completed
// payload (real neuract values + honest-blank '—', shape = the CMD V2 story args). So each card
// reads its slice straight off the payload — no host-served frame, no live mapper, no reducer.
//
// Payload shapes (the harvested Storybook story args):
//   history card (44/46): { variant, history: { data: HistoryPanelData } }
//   health  card (45):    { variant, health:  { data: HealthCardData, phaseVariant } }
//
// The sanitize* NaN-guards (the panel-overview-real-time-monitoring sanitizeSupply pattern) stay:
// every array HistoryPanel/HealthSummaryPanel `.map`s is guaranteed an array, and every scalar they
// feed a scale/Math/toFixed op is guaranteed finite — so a Layer-2-elided or honest-blanked leaf
// (missing / null / '—') renders the component's OWN blank shape (gap / dropped ref-line / empty
// strip / '—') instead of a crash or an SVG NaN. An all-blank payload → chrome + dashes, never NaN.
import { type PhaseVariant } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import type {
  HealthCardData,
  HistoryPanelData,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

// History story render: <HistoryPanel data={history.data} />
export function historyData(payload: any): HistoryPanelData | undefined {
  return payload?.history?.data;
}
// Health story render: <HealthSummaryPanel data={health.data} phaseVariant={health.phaseVariant} />
export function healthData(payload: any): HealthCardData | undefined {
  return payload?.health?.data;
}
export function healthPhaseVariant(payload: any): PhaseVariant {
  return (payload?.health?.phaseVariant as PhaseVariant) ?? "rows";
}

/* ── CMD V2's OWN honest-blank defaults (ALWAYS-DRAW last resort) ──────────────────────────────
 * ONE shared (cached) implementation in ../shared/vc-empty — re-exported so this folder's importers keep their path. */
export { unavailableHistory, unavailableHealth } from "../shared/vc-empty";

/* ── sanitize — the ONE shared implementation (../shared/vc-sanitize, F4 2026-07-12); re-exported so this
 * folder's importers keep their path. */
export { sanitizeHistory, sanitizeHealth } from "../shared/vc-sanitize";
