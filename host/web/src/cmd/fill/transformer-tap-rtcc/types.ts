// Shared host date-window + slot types for the transformer tap-rtcc fill cards.
//
// host window vocabulary (mirror of host/web/src/types.ts → DateWindow), consumed by the two chart cards'
// SamplingPicker (Voltage Regulation + Tap Activity), which re-bucket their series per-chart over the open socket:
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
export type { DateWindow, OnDateChange } from "../../../types";   // ONE declaration (host/web/src/types.ts)
