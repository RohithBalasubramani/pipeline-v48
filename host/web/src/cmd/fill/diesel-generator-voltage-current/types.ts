// Shared host date_window vocabulary + slot types for the diesel-generator voltage-current fill cards.
//
// The host date_window vocabulary (mirror of host/web/src/types.ts DateWindow):
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
//   start/end — ISO yyyy-mm-dd, only for custom-range.
export type DateWindow = { range?: string; sampling?: string; start?: string; end?: string };
export type OnDateChange = (dw: DateWindow) => void;
