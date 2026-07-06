import React from "react";
// FILL module (thin barrel) for page diesel-generator-asset-dashboard/fuel-efficiency.
// Cards 63 (Fuel Tank Anatomy — 3D), 64 (All Runs / Fuel Log), 65 (Fuel & Tank — Composite) — the three panels of the
// CMD V2 DG asset "Fuel & Efficiency" tab. Atomised into ./dg-fuel-efficiency/ — one file per card + a shared
// view-model helper + types. This barrel keeps the ./fill/*.tsx glob match (non-recursive: `*` does not cross `/`, so
// the folder files load only through here) and re-exports the CARDS registry.
//
// FRAMES=PAYLOADS [architecture]: ems_backend is RETIRED — the host emits `frames={}` EMPTY. So the ONLY data source
// is the Layer-2 `payload` (ems_exec-completed props: real neuract values + honest-blank '—'); the old live-frame /
// mapper / assetPageSocket path is DELETED. Each card renders its REAL CMD V2 component DIRECTLY from the payload.
//
// EVERY card on this page ALWAYS DRAWS [GOAL]: each renders its REAL CMD V2 component from the payload, honest-degrading
// to CMD V2's OWN empty state (structure + labels/colours + '—' / [] / empty series) when a leaf is blank — NEVER
// `return null` (a blank card), NEVER a seed mock number.
//
// DOMAIN-DATA NOTE: fuel level / rate / temp + the run log are DG telemetry the neuract logging DB does NOT carry.
// So Layer-2 honest-blanks those leaves and every card here renders CMD V2's OWN honest empty state — a 0% tank (63),
// "No runs in this period" (64), and a "No fuel data in this window." empty timeline (65). Those blank tiles are
// CORRECT: a domain slot with no neuract column renders the component's own empty state.
//
// None of the three carries a per-card date re-fetch (63 & 64 are instantaneous snapshots; 65's EngineDatePicker is
// self-contained), so this barrel passes no onDateChange.
import { card63 } from "./dg-fuel-efficiency/card-63";
import { card64 } from "./dg-fuel-efficiency/card-64";
import { card65 } from "./dg-fuel-efficiency/card-65";

export const CARDS: Record<number, (payload: any) => React.ReactNode> = {
  63: card63,
  64: card64,
  65: card65,
};
