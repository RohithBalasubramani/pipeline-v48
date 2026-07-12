// registry/fill-loader.ts — the FILL tier glob loader (split F11, 2026-07-12).
// SHARP EDGE: import.meta.glob is FILE-RELATIVE — inside this folder the pattern is "../fill/*.tsx"
// (the monolith at cmd/registry.tsx used "./fill/*.tsx").
import React from "react";

export type RenderFn = (payload: any, frame?: any, onDateChange?: (dw: any) => void, pageFrame?: any) => React.ReactNode;

// each fill module exports `CARDS: Record<card_id, (payload, frame) => ReactNode>`
const fillMods = import.meta.glob("../fill/*.tsx", { eager: true }) as Record<string, any>;
export const FILL: Record<number, RenderFn> = {};
for (const [path, m] of Object.entries(fillMods)) {
  const cards = m?.CARDS;
  if (cards && typeof cards === "object") {
    for (const [id, fn] of Object.entries(cards)) {
      if (typeof fn === "function") {
        if (FILL[Number(id)]) console.warn(`[registry] duplicate fill for card ${id} (${path})`);
        FILL[Number(id)] = fn as RenderFn;
      }
    }
  }
}
