// Shared host date-window + slot types for the transformer tap-rtcc fill cards.
//
// ems_backend window vocabulary (mirror of host/web/src/types.ts → DateWindow), consumed by the two chart cards'
// SamplingPicker (Voltage Regulation + Tap Activity), which re-bucket their series per-chart over the open socket:
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week
export type DateWindow = { range?: string; sampling?: string; start?: string; end?: string };
export type OnDateChange = (dw: DateWindow) => void;
