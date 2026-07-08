import type { CSSProperties } from "react";
import type { Card } from "../types";
import { parseCell, placementStyle, type CellPlacement } from "./cellPos";
import { countTracks } from "./tracks";
import { LAYOUT_VOCAB, type LayoutVocab } from "./vocab";

// gridPlan — PURE, DB-DRIVEN placement of a page's BODY cards (band header already lifted out) into a bounded CSS grid.
// One concern: turn each card's TEMPLATE CELL (page_layout_cards.cell) into a concrete (col,row) + the grid's row track
// string, so the whole page fits ONE viewport (equal rows, no implicit auto rows that would overflow). No per-page CSS.

export interface Seat {
  card_id: number;
  col: number;               // resolved 1-based column
  row: number;               // resolved 1-based (rebased, de-collided) row
  style: CSSProperties;      // the gridColumn/gridRow to apply to this card's cell wrapper
}
export interface GridPlan {
  seats: Seat[];
  nRows: number;             // rows actually used
  rows: string;              // gridTemplateRows to apply (template's own if it declares enough, else equal fractions)
  rowBase: number;           // header-inclusive-prose rebase that was applied
}

const bySlot = (a: Card, b: Card) => (a.slot?.slot_order ?? 0) - (b.slot?.slot_order ?? 0);

// Count declared row tracks — delegates to tracks.ts (prose / "none" / empty → 0 so the caller derives equal rows).
export { countTracks as countRowTracks } from "./tracks";

// Authored row-span height of a placement (1 unless it declares a numeric rowEnd, e.g. "row 2 / 4" → 2 rows).
const spanH = (p: CellPlacement) =>
  typeof p.rowEnd === "number" && p.row != null ? Math.max(1, p.rowEnd - p.row) : 1;

// Build the placement plan for the page's body cards, given the page's declared row tracks (may be null/one-row).
export function planGrid(cards: Card[], templateRows?: string | null, vocab: LayoutVocab = LAYOUT_VOCAB): GridPlan {
  const parsed = cards.slice().sort(bySlot).map((c) => ({ c, p: parseCell(c.slot) as CellPlacement }));

  // REBASE: header/strip band cards are lifted out of the grid by CardGrid. When the body's row prose starts at r2+
  // (never r1), it counted the band as r1 → shift every grid row down so it seats from track 1 (harmonics r2/r3 → 1/2).
  const bodyRows = parsed.map((x) => x.p.row).filter((r): r is number => r != null);
  const rowBase = bodyRows.length && Math.min(...bodyRows) >= vocab.rebase_min_row ? Math.min(...bodyRows) - 1 : 0;

  // SPAN OCCUPANCY: a col-SPANNING card ("full" / "gridColumn 1 / -1" / numeric end) occupies EVERY column it covers.
  const maxCol = Math.max(1, ...parsed.map(({ p }) =>
    Math.max(p.full ? 1 : (p.col ?? 1), typeof p.colEnd === "number" ? p.colEnd - 1 : 1)));
  const colsOf = (p: CellPlacement, col: number): number[] => {
    const start = p.full ? 1 : col;
    const end = p.full || p.colEnd === "-1" ? maxCol
              : typeof p.colEnd === "number" ? Math.max(col, p.colEnd - 1) : col;
    return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  };

  // Seat cards by a span-aware OCCUPANCY GRID (processed in slot_order):
  //  • AUTO-STACK — a card with no row prose appends to the next free row in its column(s) (column-mates never collide);
  //  • DE-COLLISION — a card whose AUTHORED (rebased) row is already taken (duplicate cells, or a nested left/right
  //    split a flat grid can't express) bumps DOWN to the next free row so nothing ever overlaps. An authored row that
  //    IS free is honored exactly (v47-parity: explicit rows win when they don't conflict).
  const occupied = new Set<string>();                                   // "col,row" cells already taken
  const colTop: Record<number, number> = {};                           // highest occupied row per column (auto append)
  const colCount: Record<number, number> = {};                         // #cards touching each column (lone detection)
  const key = (c: number, r: number) => `${c},${r}`;
  const rowsFree = (occ: number[], row: number, h: number) =>
    occ.every((k) => { for (let r = row; r < row + h; r++) if (occupied.has(key(k, r))) return false; return true; });
  const firstFree = (occ: number[], from: number, h: number) => { let r = Math.max(1, from); while (!rowsFree(occ, r, h)) r++; return r; };

  const pre = parsed.map(({ c, p }) => {
    const col = p.full ? 1 : (p.col ?? 1);
    const occ = colsOf(p, col);
    const h = spanH(p);
    const desired = p.row != null ? Math.max(1, p.row - rowBase)
                                  : 1 + Math.max(0, ...occ.map((k) => colTop[k] ?? 0));
    const row = firstFree(occ, desired, h);
    occ.forEach((k) => { for (let r = row; r < row + h; r++) occupied.add(key(k, r)); colTop[k] = Math.max(colTop[k] ?? 0, row + h - 1); colCount[k] = (colCount[k] ?? 0) + 1; });
    return { c, p, col, occ, row, h };
  });

  const nRows = Math.max(1, ...pre.map((x) => x.row + x.h - 1));

  // Honor the template's own row tracks ONLY if it declares enough for what we use; else derive equal viewport rows.
  const declared = countTracks(templateRows);
  const rows = declared >= nRows && countTracks(templateRows) > 0 ? (templateRows as string).trim()
                                                                  : `repeat(${nRows}, minmax(0, 1fr))`;

  const seats: Seat[] = pre.map(({ c, p, col, occ, row, h }) => {
    // A card ALONE in its column spans every row (full-height side rail — power-quality card 47 "col 1 (aside)", and
    // "col 2 / full" whose column holds only it). v47-parity precedence: an EXPLICITLY AUTHORED row ALWAYS wins — lone
    // never overrides p.row (DG-1 RTM card 38 "gridRow 2" stays row 2); "alone" means NO other card touches ANY column
    // this card covers (span occupancy). Explicit spans (rowEnd/full) also win.
    const lone = p.row == null && nRows > 1 && p.rowEnd == null && !p.full && occ.every((k) => colCount[k] === 1);
    // gridRow is built from the RESOLVED (rebased + de-collided) row, never the raw p.row — a bumped card must render
    // where it was actually seated. gridColumn keeps the parsed col-span ("1 / -1", "1 / 3"); de-collision never moves
    // columns. A numeric rowEnd span shifts with the bumped start (row → row + height).
    const gridColumn = (placementStyle(p, rowBase).gridColumn as any) ?? col;
    const gridRow = lone ? "1 / -1" : typeof p.rowEnd === "number" ? `${row} / ${row + h}` : row;
    const style: CSSProperties = p.full ? { gridColumn: "1 / -1", gridRow: row } : { gridColumn, gridRow };
    return { card_id: c.card_id, col, row, style };
  });

  return { seats, nRows, rows, rowBase };
}
