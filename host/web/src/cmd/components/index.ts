import type React from "react";

// PER-FAMILY COMPONENT BARRELS — the same discovery pattern as ../fill/*.tsx: every sibling barrel in this folder
// exports `COMPONENTS: Record<card_id, Component>` (the card's REAL CMD_V2 component, rendered directly from its
// completed payload) and is DISCOVERED here via import.meta.glob. Adding a page family's cards = dropping ONE new
// barrel file beside the others — no edit to this merge point, none to the registry. Duplicate card ids warn and
// last-alphabetical wins (mirrors the FILL merge in ../registry.tsx).
const barrels = import.meta.glob(["./*.ts", "./*.tsx", "!./index.ts"], { eager: true }) as Record<string, any>;

export const COMPONENTS: Record<number, React.ComponentType<any>> = {};
for (const [path, m] of Object.entries(barrels)) {
  const cards = m?.COMPONENTS;
  if (cards && typeof cards === "object") {
    for (const [id, comp] of Object.entries(cards)) {
      if (COMPONENTS[Number(id)]) console.warn(`[components] duplicate component for card ${id} (${path})`);
      COMPONENTS[Number(id)] = comp as React.ComponentType<any>;
    }
  }
}
