// Shared host date-window type for the panel-overview/energy-power fill cards.
//
// ems_backend window vocabulary (host/src/types.ts → DateWindow):
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
export type DateWindow = { range?: string; sampling?: string; start?: string; end?: string };
