import React from "react";
// FILL module (thin barrel) for page diesel-generator-asset-dashboard/operations-runtime.
// Only cards 71 (Runtime & Duty) + 73 (Power Energy Analysis) fall here. Cards 70 (Live Operations & Runtime) +
// 72 (Energy & Reliability) render DIRECTLY from their Layer-2 payload via COMPONENTS (Cmp70 LiveOpsCard /
// Cmp72 EnergyReliabilityCard) — `renderCmd` reaches COMPONENTS BEFORE FILL, so FILL[70]/[72] entries were dead
// duplicates and have been DELETED (with their card-70.tsx / card-72.tsx files).
// Atomised into ./dg-operations-runtime/ — one file per card + shared helpers (view-model / date-wiring / types).
// This barrel keeps the ./fill/*.tsx glob match (non-recursive: `*` does not cross `/`, so the folder files are only
// loaded through here) and re-exports the CARDS registry. Filename matches the row's cmd_catalog.card_render_map
// .fill_module (`host/web/src/cmd/fill/dg-operations-runtime.tsx`).
//
// FRAMES=PAYLOADS [architecture]: host-served is RETIRED — the host emits `frames={}` EMPTY. So the ONLY data source is
// the Layer-2 `payload`; the old live-frame / energy-power column-row reducer / OpsFrame-from-frame machinery is
// DELETED. Card 71 renders whatever `duty` slice Layer-2 emitted (real or honest-blank '—') over CMD V2's OWN empty
// view-model; its run-log rows have NO neuract source so are always the empty RunsView ("No runs in this period").
//
// Card 73 (Power Energy Analysis) has NO Storybook story in card_payloads — it is rendered from metadata + honest-empty
// (demand-limit nameplate line + empty buckets), NOT from a harvested seed payload. EVERY card ALWAYS DRAWS its real
// CMD V2 chrome — NEVER `return null` (a blank card), NEVER a seed/mock number.
import { card71 } from "./dg-operations-runtime/card-71";
import { card73 } from "./dg-operations-runtime/card-73";
import type { OnDateChange } from "./dg-operations-runtime/types";

// Cards 71 (Runtime & Duty) & 73 (Power Energy Analysis) each own a SamplingPicker that drives onDateChange (a no-op
// re-fetch now that host-served is retired, but the control is real CMD V2 chrome).
export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: OnDateChange) => React.ReactNode
> = {
  71: card71,
  73: card73,
};
