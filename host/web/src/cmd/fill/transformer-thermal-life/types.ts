// Shared host date-window + slot types for the transformer thermal-life fill cards.
//
// The two history cards (76 Thermal Timeline, 77 Insulation Aging) carry a CMD V2 `SamplingPicker`. Its `onRequest`
// (chart, {range, sampling}) re-buckets that chart over the open socket; on the V48 host we translate that into the
// host window vocabulary the host re-fetches the card's frame against. (Mirror of host/web/src/types.ts →
// DateWindow — the same shape the feeder fills use.)
//   range    ∈ today | yesterday | last-7-days | this-month | last-month | custom-range
//   sampling ∈ hour | hourly | day | week
export type { DateWindow, OnDateChange } from "../../../types";   // ONE declaration (host/web/src/types.ts)
