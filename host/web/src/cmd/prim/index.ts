// prim/index.ts — the PRIMITIVES-ONLY card registry. [primitives-only port]
//
// USER DIRECTIVE (2026-07-12): no page cards. Each family file under prim/ exports a card_id-keyed CARDS record of
// renderers that mount CMD_V2 chart PRIMITIVES directly from the completed payload (docs/primitives_inventory/
// PORT_CONTRACT.md). DISCOVERY IS GLOB-DRIVEN (the fill-loader pattern): a new family = a new file exporting CARDS —
// no edit here, so parallel ports never collide. renderCmd's PRIM tier consults this registry; ids absent here fall
// through to the legacy tiers ONLY while the port is in flight — the end state deletes those tiers.
import type React from "react";

export type PrimRenderer = (payload: any, onDateChange?: (dw: any) => void) => React.ReactNode;

const modules = import.meta.glob("./*.tsx", { eager: true }) as Record<string, any>;

export const PRIM: Record<number, PrimRenderer> = {};
for (const path of Object.keys(modules).sort()) {
  const cards = modules[path]?.CARDS;
  if (cards && typeof cards === "object") Object.assign(PRIM, cards);
}
