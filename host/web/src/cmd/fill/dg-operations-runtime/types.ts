// Shared host date-window + slot types for the DG operations-runtime fill cards.
//
// Page: diesel-generator-asset-dashboard/operations-runtime. Cards 70 LiveOpsCard,
// 71 RuntimeDutyPanel, 72 EnergyReliabilityCard, 73 Power Energy Analysis.
//
// host window vocabulary (mirror of host/web/src/types.ts → DateWindow):
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
export type { DateWindow, OnDateChange } from "../../../types";   // ONE declaration (host/web/src/types.ts)
