// Shared host date_window vocabulary for the diesel-generator-voltage-current fill cards — ONE declaration
// (host/web/src/types.ts), re-exported here so this folder's importers keep their path.
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
//   start/end — ISO yyyy-mm-dd, only for custom-range.
export type { DateWindow, OnDateChange } from "../../../types";
