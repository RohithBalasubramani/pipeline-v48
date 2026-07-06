import React from "react";
// FILL module (thin barrel) for page individual-feeder-meter-shell/real-time-monitoring.
// Cards 36 (Power & Energy), 37 (Voltage Monitor), 38 (Current Monitor) — all three panels
// on the CMD V2 RealTimeMonitoringTab. Atomised into ./feeder-real-time-monitoring/ —
// one file per card + shared payload readers (payload-unwrap / types).
//
// PAYLOAD-DIRECT (ems_backend RETIRED — the host emits frames={} EMPTY): the ONLY data
// source is the Layer-2 completed `payload` ({ data, freshness } — real neuract values +
// honest-blank '—', shaped as the CMD V2 panel props). Each card renders its panel straight
// from that payload; a missing leaf degrades to the CMD V2 "unavailable" view-model slice
// (structured, empty series → "—", NEVER mock). The old ems_backend frame→reducer→mapper
// path (frame-view-model.ts) is dead code now and was DELETED.
//
// ALWAYS-DRAW: each card renders real values when the payload carries them and structured
// "—" placeholders otherwise — it NEVER returns null (a null = a blank card, forbidden).
//
// This barrel keeps the ./fill/*.tsx glob match and re-exports the CARDS registry.
import { card36 } from "./feeder-real-time-monitoring/card-36";
import { card37 } from "./feeder-real-time-monitoring/card-37";
import { card38 } from "./feeder-real-time-monitoring/card-38";

// Real-time monitoring is LIVE-only — the three panels carry NO date/range/sampling
// control, so these cards take no onDateChange (1-arg payload-only signature).
export const CARDS: Record<number, (payload: any) => React.ReactNode> = {
  36: card36,
  37: card37,
  38: card38,
};
