import React from "react";
// FILL module (thin barrel) for page individual-feeder-meter-shell/voltage-current.
// Cards 44 (Voltage History), 45 (Current Health Summary), 46 (Current History) — all on the
// CMD V2 Equipment-Detail "Voltage & Current" tab. Atomised into ./feeder-voltage-current/ —
// one file per card + shared helpers (payload-unwrap / date-wiring / types). FRAMES ARE RETIRED:
// each card renders its REAL CMD V2 component DIRECTLY from the Layer-2 payload (no ems_backend
// frame, no live mapper). This barrel keeps the ./fill/*.tsx glob match and re-exports CARDS.
import { card44 } from "./feeder-voltage-current/card-44";
import { card45 } from "./feeder-voltage-current/card-45";
import { card46 } from "./feeder-voltage-current/card-46";
import type { OnDateChange } from "./feeder-voltage-current/types";

// Card 45 (Current Health Summary) renders HealthSummaryPanel — a live health
// snapshot with NO date/range/sampling control — so it carries no onDateChange.
export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: OnDateChange) => React.ReactNode
> = {
  44: card44,
  45: card45,
  46: card46,
};
