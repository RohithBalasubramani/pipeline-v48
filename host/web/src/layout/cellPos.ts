import type { CSSProperties } from "react";
import type { Slot } from "../types";

// page_layout_cards.cell is hand-authored prose with MANY shapes across pages (all live pages surveyed):
//   "r1 c1" · "row 1 / col 1" · "row 2 / col 2 (or full)" · "col 1" · "col 2 / nested row 1"
//   "col 2 / stack row 2 / left" · "gridColumn 1 / -1; gridRow 1" · "r2 left" / "r3 right" · "1 / 2" · "col 1 (aside)"
// We parse it into a normalized placement {col, row, colEnd, rowEnd} — then the grid seats each card by that placement
// and (crucially) auto-sizes its rows to the MAX row used so nothing overflows the viewport. {} col/row → auto-flow.
//
// CELL-DATA is the single source of truth for WHERE a card sits; the grid template only supplies track SIZES.

export interface CellPlacement {
  col?: number;          // 1-based grid column (start)
  row?: number;          // 1-based grid row (start) — REBASED (see below): the header-band row is not a grid row
  colEnd?: number | "-1"; // explicit column end/span ("1 / -1" full-bleed)
  rowEnd?: number | "-1"; // explicit row end/span
  full?: boolean;        // "full" / "full-bleed" — span every column of the current row
}

// A "row 1" reference in the CELL prose counts the header/strip row as r1 (it reads as a full-width band above the
// grid). But that band card is lifted OUT of the grid (see CardGrid.isBand), so every remaining grid card's row must
// be REBASED down by 1 (header r2/r3 → grid rows 1/2). rowBase is the number of leading band rows to subtract.
export function parseCell(slot?: Slot | null): CellPlacement {
  const s = (typeof slot?.cell === "string" ? slot.cell : "").toLowerCase().trim();
  const out: CellPlacement = {};
  if (!s) return out;

  // "full" anywhere (full / full-bleed / (or full)) — the WIDTH-span meaning is resolved AFTER col/row are parsed
  // (see below): it only spans the full width when NO explicit column was authored.
  const fullTok = /\bfull(-bleed)?\b/.test(s);

  // --- explicit CSS span:  "gridcolumn 1 / -1"  ·  "col 2 / -1" ---
  const colSpan = /(?:gridcolumn|column|col|c)\s*(\d+)\s*\/\s*(-?\d+)/.exec(s);
  if (colSpan) { out.col = Number(colSpan[1]); out.colEnd = colSpan[2] === "-1" ? "-1" : Number(colSpan[2]); }
  else {
    // bare "1 / 2" (row / col shorthand: first number is ROW, second is COL) — only when there is no col/row keyword.
    const bare = /^\s*(\d+)\s*\/\s*(\d+)\s*$/.exec(s);
    if (bare && !/[a-z]/.test(s)) { out.row = Number(bare[1]); out.col = Number(bare[2]); }
    const col = /(?:gridcolumn|column|col|c)\s*(\d+)/.exec(s);
    if (col) out.col = Number(col[1]);
    else if (out.col == null && /\bleft\b/.test(s)) out.col = 1;
    else if (out.col == null && /\bright\b/.test(s)) out.col = 2;
  }

  // --- row: explicit CSS span first, then a plain row number, then a NESTED/STACK row (a card stacked within its
  //     column IS its own outer grid row here — there is one CARD per stack entry, not one nested card). ---
  const rowSpan = /(?:gridrow|row|r)\s*(\d+)\s*\/\s*(-?\d+)/.exec(s);
  if (rowSpan && out.row == null) { out.row = Number(rowSpan[1]); out.rowEnd = rowSpan[2] === "-1" ? "-1" : Number(rowSpan[2]); }
  else if (out.row == null) {
    // "nested row N" / "stack row N" — the Nth entry stacked in this card's column → outer grid row N.
    const nested = /(?:nested|stack)\s+row\s*(\d+)/.exec(s);
    if (nested) out.row = Number(nested[1]);
    else {
      const row = /(?:gridrow|row|r)\s*(\d+)/.exec(s);
      if (row) out.row = Number(row[1]);
    }
  }

  // "full" spans the whole WIDTH — but ONLY when no explicit column was authored (bare "full" / "full-bleed"). With an
  // explicit column present ("col 2 / full") a width-span would wrongly cover the OTHER column's cards, so we keep the
  // column and let the grid's lone-rule stretch the card down its own column (full-HEIGHT). With an explicit row too
  // ("row 2 / col 2 (or full)") it is a soft annotation — the card just seats at its (col,row).
  if (fullTok && out.col == null) out.full = true;
  return out;
}

// Convert a normalized placement into CSS grid props, applying the header rebase (rowBase leading band rows removed).
export function placementStyle(p: CellPlacement, rowBase = 0): CSSProperties {
  const out: CSSProperties = {};
  if (p.full) { out.gridColumn = "1 / -1"; }
  else if (p.col != null) out.gridColumn = p.colEnd != null ? `${p.col} / ${p.colEnd}` : p.col;
  if (p.row != null) {
    const r = Math.max(1, p.row - rowBase);
    out.gridRow = p.rowEnd != null ? `${r} / ${p.rowEnd}` : r;
  }
  return out;
}

// Back-compat shim (kept so any other importer still works): parse + place with no rebase/span awareness.
export function cellPos(slot?: Slot | null): CSSProperties {
  return placementStyle(parseCell(slot));
}
