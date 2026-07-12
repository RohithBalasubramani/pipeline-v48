import React from "react";
// FILL module (thin barrel) for page individual-feeder-meter-shell/energy-power.
// Cards 39 (Today's Energy), 40 (Power Energy Analysis), 41 (Input vs Output Energy), 42 (Load Anomalies) — the four
// panels of the CMD V2 Equipment-Detail "Energy & Power" tab. Atomised into ./feeder-energy-power/ — one file per card
// + shared helpers (view-model / date-wiring / types). This barrel keeps the ./fill/*.tsx glob match (non-recursive:
// `*` does not cross `/`, so the folder files are only loaded through here) and re-exports the CARDS registry.
//
// FRAMES ARE RETIRED: each card renders its REAL CMD V2 component DIRECTLY from the Layer-2 payload (`{ variant, data }`)
// — no host-served frame, no live mapper. EVERY card ALWAYS DRAWS [GOAL]: real values from the payload slice, else
// honest-degrades to CMD V2's OWN empty-but-valid view-model (structure + typed-empty, all labels/colours) — NEVER
// `return null` (a blank card), NEVER a seed mock number.
//
// Cards 40 & 41 are the SAME two equipment-detail cards the panel-overview/energy-power page also lists. The registry
// is card_id-keyed GLOBALLY, so these OWN their identity here (always-draws + a synthesized input/output for
// non-HV/LV feeders); the panel-overview barrel no longer re-exports 40/41 to avoid a duplicate registration.
import { card39 } from "./feeder-energy-power/card-39";
import { card40 } from "./feeder-energy-power/card-40";
import { card41 } from "./feeder-energy-power/card-41";
import { card42 } from "./feeder-energy-power/card-42";
import type { OnDateChange } from "./feeder-energy-power/types";

// Card 41 (Input vs Output Energy) renders an instantaneous snapshot with NO date/range control — so it carries no
// onDateChange. The other three each own a period control that drives a per-card re-fetch.
export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: OnDateChange) => React.ReactNode
> = {
  39: card39,
  40: card40,
  41: card41,
  42: card42,
};
