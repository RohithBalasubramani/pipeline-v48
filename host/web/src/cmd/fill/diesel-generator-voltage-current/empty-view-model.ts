// honest-blank (structured-empty) slices for the diesel-generator voltage-current fill cards.
//
// ems_backend is RETIRED → `frame` is always empty and each card renders its OWN Layer-2 payload (real neuract values +
// honest-blank '—'). This module is the LAST-RESORT ALWAYS-DRAW fallback: when a card's payload carries no usable slice
// (Layer 2 skipped, or a pure honest-blank skeleton with the metrics/series leaf elided) we render CMD V2's OWN
// structured-empty slice so the panel draws its chrome + '—' instead of a blank/null card. It is built by the shared
// electrical `createUnavailableVoltageCurrentViewModel` (the SAME single-source empty producer the live V&C screens use)
// — never a fabricated/seed number.
import { createUnavailableVoltageCurrentViewModel } from "@cmd-v2/pages/electrical/tabs/voltage-current/voltageCurrentViewModel";
import type {
  HealthCardData,
  HistoryPanelData,
  VoltageCurrentViewModel,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

let _empty: VoltageCurrentViewModel | null = null;
/** CMD V2's OWN structured-empty view-model (all four slices: series [], metrics/phases/stats with '—', chart frames
 *  preserved). Cached; pure. The ALWAYS-DRAW default when a card's payload produced no usable slice — the panels render
 *  their chrome + honest '—' instead of a blank/null card. NEVER a fabricated/seed number. */
function unavailableViewModel(): VoltageCurrentViewModel {
  if (_empty) return _empty;
  _empty = createUnavailableVoltageCurrentViewModel({ source: "api", availability: "unavailable" } as any);
  return _empty;
}

/** The structured-empty `HistoryPanelData` for a card (voltage or current) — draws chrome + '—' when there's no data. */
export function unavailableHistory(which: "voltage" | "current"): HistoryPanelData {
  const vm = unavailableViewModel();
  return which === "voltage" ? vm.voltageHistory : vm.currentHistory;
}

/** The structured-empty `HealthCardData` for a card (voltage or current) — draws chrome + '—' when there's no data. */
export function unavailableHealth(which: "voltage" | "current"): HealthCardData {
  const vm = unavailableViewModel();
  return which === "voltage" ? vm.voltageHealth : vm.currentHealth;
}
