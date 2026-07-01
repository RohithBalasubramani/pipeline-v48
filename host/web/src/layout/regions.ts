import type { Card } from "../types";

// A "band" region spans the full page width above the grid (page header / control strip).
export function isBand(region?: string | null): boolean {
  const r = (region || "").toLowerCase();
  return r === "strip" || r === "header" || r === "top";
}

// region → 0-based column for the FLEX layout (RTM). left/main → main column; right/rail → the rail column.
export function regionColumn(region?: string | null): number {
  const r = (region || "main").toLowerCase();
  if (r === "right" || r === "rail") return 1;
  return 0;
}

const slotOrder = (c: Card) => c.slot?.slot_order ?? 0;

// Group region-based (flex) cards into N ordered columns (by slot_order). Returns columns[colIndex] = cards.
export function columnize(cards: Card[], nCols: number): Card[][] {
  const cols: Card[][] = Array.from({ length: nCols }, () => []);
  for (const c of cards) {
    const i = Math.min(regionColumn(c.slot?.region), nCols - 1);
    cols[i].push(c);
  }
  for (const col of cols) col.sort((a, b) => slotOrder(a) - slotOrder(b));
  return cols;
}
