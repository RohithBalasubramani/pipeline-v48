import React from "react";
// FILL module (thin barrel) for page transformer-asset-dashboard/thermal-life.
// Cards 74 (Thermal Life), 75 (Life & Capacity), 76 (Thermal Timeline), 77 (Insulation Aging & Loss of Life) — the four
// panels of the CMD V2 Transformer "Thermal & Life" tab. Atomised into ./transformer-thermal-life/ — one file per card
// + shared helpers (view-model / date-wiring / types). This barrel keeps the ./fill/*.tsx glob match (non-recursive:
// `*` does not cross `/`, so the folder files are only loaded through here) and re-exports the CARDS registry.
//
// EVERY card on this page ALWAYS DRAWS [GOAL]: each reshapes the LIVE `lt-transformer-thermal` widget-envelope into the
// CMD V2 ThermalLifeFrame and runs the card's OWN producer buildThermalLifeViewModel (no re-implemented transform),
// then honest-degrades to that same producer's typed-empty view-model when the frame lacks a value — NEVER `return
// null` (a blank card), NEVER a seed mock number. Load% / loss / efficiency / derating are electrical-derivable and
// fill REAL; the thermal (winding/oil/hotspot temperature) + insulation-aging (FAA / loss-of-life) domain slots have no
// neuract column today and render the component's empty state (blank plot / dropped metric), which is correct.
import { card74 } from "./transformer-thermal-life/card-74";
import { card75 } from "./transformer-thermal-life/card-75";
import { card76 } from "./transformer-thermal-life/card-76";
import { card77 } from "./transformer-thermal-life/card-77";
import type { OnDateChange } from "./transformer-thermal-life/types";

// Cards 74 (Thermal Life) & 75 (Life & Capacity) render instantaneous snapshots with NO date/range control — so they
// carry no onDateChange (2-arg). Cards 76 (Thermal Timeline) & 77 (Insulation Aging) each own a SamplingPicker that
// drives a per-card re-fetch.
export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: OnDateChange) => React.ReactNode
> = {
  74: card74,
  75: card75,
  76: card76,
  77: card77,
};
