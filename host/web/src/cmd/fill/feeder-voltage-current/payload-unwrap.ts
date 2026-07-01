// payload unwrap (story args → component props) for the feeder voltage-current fill cards.
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
