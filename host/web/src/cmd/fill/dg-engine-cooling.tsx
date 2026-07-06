import React from "react";
// FILL module (thin barrel) for page diesel-generator-asset-dashboard/engine-cooling.
// Cards 61 (Thermal Timeline), 62 (Pressure·Speed·Load) — two of the three cards of the DG asset "Engine & Cooling" tab
// (CMD V2 pages/assets/diesel-generator/tabs/engine-cooling). Atomised into ./dg-engine-cooling/ — one file per card +
// a shared view-model helper. This barrel keeps the ./fill/*.tsx glob match (non-recursive: `*` does not cross `/`, so
// the folder files are only loaded through here) and re-exports the CARDS registry.
//
// Card 60 (Engine 3D Callout Viewer) is NOT here: its completed payload is an asset_3d viewer ENVELOPE, so it renders
// via SPECIAL[60] (Asset3dEnvelope → ComingSoon3D) — which `renderCmd` reaches BEFORE FILL. A FILL[60] entry was a dead
// duplicate of that envelope render and has been DELETED.
//
// FRAMES=PAYLOADS [architecture]: ems_backend is RETIRED — the host emits `frames={}` EMPTY. So the ONLY data source is
// the Layer-2 `payload`; the old live-frame / mapper / assetPageSocket path is DELETED. Cards 61+62 render CMD V2's REAL
// <Panel> via the tab's OWN buildEngineCoolingViewModel, overlaying the payload's real `chart` chrome onto CMD V2's OWN
// typed-empty (all-zero) view-model — NEVER `return null` (a blank card), NEVER a seed/mock number (and NEVER CMD V2's
// demo generator getEngineMockFrame).
//
// DATA REALITY [honest-blank]: all engine metrics (coolant/oil/intake/exhaust temp, oil pressure, engine speed, load%)
// are ENGINE-DOMAIN telemetry with NO neuract columns — so Layer-2 carries no series points and cards 61+62 draw their
// FULL structure with an EMPTY timeline (the component's own empty state), the correct blank-tile behaviour for a
// domain slot with no live source.
import { card61 } from "./dg-engine-cooling/card-61";
import { card62 } from "./dg-engine-cooling/card-62";

// Neither card wires onDateChange: 61/62 carry only the cosmetic EngineDatePicker baked inside CMD V2's <Panel> (no
// re-fetchable neuract history endpoint for this domain telemetry).
export const CARDS: Record<number, (payload: any) => React.ReactNode> = {
  61: card61,
  62: card62,
};
