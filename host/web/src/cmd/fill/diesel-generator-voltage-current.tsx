import React from "react";
// FILL module (thin barrel) for page diesel-generator-asset-dashboard/voltage-current.
// Cards 66 (Voltage Live Health), 67 (Voltage History), 68 (Current Live Health), 69 (Current
// History) — the four panels of the CMD V2 Diesel-Generator "Voltage & Current" tab
// (DgVoltageCurrentCards.stories.tsx). Atomised into ./diesel-generator-voltage-current/ — one file
// per card + shared helpers (frame-view-model / payload-unwrap / date-wiring / types). This barrel
// keeps the ./fill/*.tsx glob match (non-recursive: `*` does not cross `/`, so the folder files are
// only loaded through here) and re-exports the CARDS registry.
//
// FULLY ELECTRICAL page: every card fills REAL live values from the neuract voltage/current column
// (`voltage-current` column-row) + history (`voltage-history` / `current-history` bucket) frames the
// host binds — via the SHARED electrical mapper + view-model (the same producer the DG tab viewModel
// emits: the shared `VoltageCurrentViewModel`). Honest-degrades to CMD V2's OWN structured-empty
// view-model when the frame is missing/unmappable — NEVER `return null` (a blank card), NEVER a seed
// mock number. See ./diesel-generator-voltage-current/frame-view-model.ts for why the shared electrical
// mapper (not the DG tab's own backend2 AssetPageFrame mapper) is the right live producer here.
import { card66 } from "./diesel-generator-voltage-current/card-66";
import { card67 } from "./diesel-generator-voltage-current/card-67";
import { card68 } from "./diesel-generator-voltage-current/card-68";
import { card69 } from "./diesel-generator-voltage-current/card-69";
import type { OnDateChange } from "./diesel-generator-voltage-current/types";

// Cards 66 & 68 (Voltage / Current Live Health) render HealthSummaryPanel — a live health snapshot
// with NO date/range/sampling control — so they carry no onDateChange. Cards 67 & 69 (Voltage /
// Current History) each own a SamplingPicker that drives a per-card re-fetch via onDateChange.
export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: OnDateChange) => React.ReactNode
> = {
  66: card66,
  67: card67,
  68: card68,
  69: card69,
};
