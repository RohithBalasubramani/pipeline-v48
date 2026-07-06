// Shared host date-window + slot types for the feeder energy-power fill cards.
//
// ems_backend window vocabulary (mirror of host/web/src/types.ts → DateWindow):
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
export type DateWindow = { range?: string; sampling?: string; start?: string; end?: string };
export type OnDateChange = (dw: DateWindow) => void;
