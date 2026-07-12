// The ONE structured-empty (honest-blank) V&C view-model — previously duplicated by the feeder and the
// diesel-generator voltage-current fill folders (the DG copy memoized, the feeder copy rebuilt the whole VM on every
// honest-blank render). Built by CMD V2's OWN `createUnavailableVoltageCurrentViewModel` (the same single-source
// empty producer the live V&C screens use): series [], metrics/phases/stats '—', chart frames preserved — the
// ALWAYS-DRAW last resort when a card's payload carries no usable slice. NEVER a fabricated/seed number.
import { createUnavailableVoltageCurrentViewModel } from "@cmd-v2/pages/electrical/tabs/voltage-current/voltageCurrentViewModel";
import type {
  HealthCardData,
  HistoryPanelData,
  VoltageCurrentViewModel,
} from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

let _empty: VoltageCurrentViewModel | null = null;
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
