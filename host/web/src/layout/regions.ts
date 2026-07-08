import type { Card } from "../types";
import { isBandRegion, LAYOUT_VOCAB, type LayoutVocab } from "./vocab";

// regions.ts — ONE concern: interpret a card's page_layout_cards.region into layout SEMANTICS (band vs body, rail vs
// main). The vocabulary is DB-driven (see ./vocab); this file only applies it. GENERIC — no page name / card id.

// A "band" region spans the full page width above the grid (page header / control strip / intent banner). Delegates to
// the DB-tunable band set (LAYOUT_VOCAB.band_regions ⊇ {strip, header, top, banner}); pass a resolved vocab to honor
// a per-response DB override.
export function isBand(region?: string | null, vocab: LayoutVocab = LAYOUT_VOCAB): boolean {
  return isBandRegion(region, vocab);
}

// region → 0-based column for a REGION-DRIVEN (flex) layout. rail set → the rail (col 1); everything else → main (col 0).
export function regionColumn(region?: string | null, vocab: LayoutVocab = LAYOUT_VOCAB): number {
  const r = (region || "main").toLowerCase().trim();
  return vocab.rail_regions.includes(r) ? 1 : 0;
}

const slotOrder = (c: Card) => c.slot?.slot_order ?? 0;

// Group region-based (flex) cards into N ordered columns (by slot_order). Returns columns[colIndex] = cards.
export function columnize(cards: Card[], nCols: number, vocab: LayoutVocab = LAYOUT_VOCAB): Card[][] {
  const cols: Card[][] = Array.from({ length: nCols }, () => []);
  for (const c of cards) {
    const i = Math.min(regionColumn(c.slot?.region, vocab), nCols - 1);
    cols[i].push(c);
  }
  for (const col of cols) col.sort((a, b) => slotOrder(a) - slotOrder(b));
  return cols;
}
