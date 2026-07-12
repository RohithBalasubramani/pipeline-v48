import React from "react";
// FILL module (thin barrel) for page transformer-asset-dashboard/tap-rtcc.
// Cards 78 (Tap Position Optimization), 79 (Voltage Regulation Timeline), 80 (Recent Tap Changes), 81 (Tap Activity &
// Wear) — the four cards of the CMD V2 Transformer "Tap & RTCC" tab (TapRtccTab). Atomised into ./transformer-tap-rtcc/
// — one file per card + shared helpers (view-model / date-wiring / types). This barrel keeps the ./fill/*.tsx glob
// match (non-recursive: `*` does not cross `/`, so the folder files are only loaded through here) and re-exports the
// CARDS registry.
//
// ALL FOUR cards share ONE live host-served asset-page frame and ONE shared view-model — mirroring the CMD V2 tab,
// which builds every card from a single frame via `mapTapRtccToFrame` → `buildTapRtccViewModel` (REUSED here, never
// re-implemented). The regulation card (79) is the ELECTRICAL one — the regulated bus voltage is a real neuract
// measurement, so it fills for real once the frame carries the AVR setpoint. Tap position (78), recent changes (80)
// and tap activity (81) are DOMAIN slots with no neuract column today → they HONEST-DEGRADE to the tab's OWN empty
// chrome (gauge/points/rows blanked, KPIs "—", real labels/axes/colours) so each STILL DRAWS — never a blank/null
// card, never a fabricated/seed number.
import { card78 } from "./transformer-tap-rtcc/card-78";
import { card79 } from "./transformer-tap-rtcc/card-79";
import { card80 } from "./transformer-tap-rtcc/card-80";
import { card81 } from "./transformer-tap-rtcc/card-81";
import type { OnDateChange } from "./transformer-tap-rtcc/types";

// Cards 78 (gauge) & 80 (change-log table) carry no header period control → no onDateChange. Cards 79 & 81 each own a
// SamplingPicker that drives a per-card re-fetch via onDateChange.
export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: OnDateChange) => React.ReactNode
> = {
  78: card78,
  79: card79,
  80: card80,
  81: card81,
};
