// Shared host date-window + slot types for the feeder energy-power fill cards.
//
// host window vocabulary (mirror of host/web/src/types.ts → DateWindow):
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
export type { DateWindow, OnDateChange } from "../../../types";   // ONE declaration (host/web/src/types.ts)
