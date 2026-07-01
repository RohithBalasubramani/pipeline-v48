import type { CSSProperties } from "react";
import type { Slot } from "../types";

// page_layout_cards.cell is hand-authored prose with MANY shapes across pages:
//   "r1 c1" · "row 1 / col 1" · "row 2 / col 2 (or full)" · "col 1" · "col 2 / nested row 1"
//   "gridColumn 1 / -1; gridRow 1" · "r2 left" / "r3 right"
// Parse the row/col (and CSS spans like "1 / -1") best-effort → real grid placement; {} when unparseable (auto-flow).
export function cellPos(slot?: Slot | null): CSSProperties {
  const s = (typeof slot?.cell === "string" ? slot.cell : "").toLowerCase();
  if (!s) return {};
  const out: CSSProperties = {};

  // --- column: explicit CSS span first ("gridcolumn 1 / -1"), then a bare number, then left/right keyword ---
  const colSpan = /(?:gridcolumn|column|col|c)\s*(\d+)\s*\/\s*(-?\d+)/.exec(s);
  if (colSpan) out.gridColumn = `${colSpan[1]} / ${colSpan[2]}`;
  else {
    const col = /(?:gridcolumn|column|col|c)\s*(\d+)/.exec(s);
    if (col) out.gridColumn = Number(col[1]);
    else if (/\bleft\b/.test(s)) out.gridColumn = 1;
    else if (/\bright\b/.test(s)) out.gridColumn = 2;
  }

  // --- row: skip "nested row" (that's an inner grid the card owns, not its own track) ---
  if (!/nested\s+row/.test(s)) {
    const rowSpan = /(?:gridrow|row|r)\s*(\d+)\s*\/\s*(-?\d+)/.exec(s);
    if (rowSpan) out.gridRow = `${rowSpan[1]} / ${rowSpan[2]}`;
    else {
      const row = /(?:gridrow|row|r)\s*(\d+)/.exec(s);
      if (row) out.gridRow = Number(row[1]);
    }
  }
  return out;
}
