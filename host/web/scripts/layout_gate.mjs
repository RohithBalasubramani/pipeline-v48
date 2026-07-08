// scripts/layout_gate.mjs — SINGLE-VIEWPORT LAYOUT GATE. Verifies the grid-placement plan (src/layout/gridPlan.ts)
// seats every page's cards by their TEMPLATE CELLS into a bounded grid that fits ONE viewport — no two cards collide in
// the same cell, no card is orphaned into an implicit overflow row, and the row-track count equals the rows actually
// used. Data-driven: each case mirrors the real cmd_catalog page_layout_cards rows for that page (see the SQL in the
// task). GENERIC — the assertions exercise gridPlan, not per-page CSS.
//   Run:  npm run layout-gate
import { planGrid, countRowTracks } from "../src/layout/gridPlan.ts";
import { isBand } from "../src/layout/regions.ts";

// A minimal Card shape (only slot.cell + slot.slot_order matter to planGrid).
const card = (id, order, cell, region) => ({ card_id: id, slot: { slot_order: order, cell, region } });

// Each case: {name, templateRows (page_specs.grid_template_rows), band-lifted body cards, expected seats}.
// "band-lifted" = we pass ONLY the non-band cards (CardGrid pulls header/strip/footer out before RealGrid), exactly
// like production. Expected = {card_id: "col,row"} after placement (row already rebased).
const cases = [
  {
    name: "DG-1 RTM (individual-feeder-meter-shell/real-time-monitoring) — full-width r1 + 2 explicit r2 cards",
    templateRows: "1fr 1fr",                        // page_specs.grid_template_rows for the page
    cards: [                                        // exact cmd_catalog page_layout_cards rows (cards 36/37/38)
      card(36, 1, "gridColumn 1 / -1; gridRow 1", "main"),
      card(37, 2, "gridColumn 1; gridRow 2", "main"),
      card(38, 3, "gridColumn 2; gridRow 2", "main"),
    ],
    expectRows: 2,
    expect: {
      36: { col: 1, row: 1, gridColumn: "1 / -1", gridRow: "1" },
      37: { col: 1, row: 2, gridRow: "2" },
      38: { col: 2, row: 2, gridRow: "2" },         // THE BUG: lone-rule stretched 38 to "1 / -1", covering 36's right half
    },
  },
  {
    name: "AHU-8 power-quality (individual-feeder-meter-shell/power-quality) — 3 cards",
    templateRows: "minmax(0, 1fr)",                 // template declares ONE row; plan must derive TWO for the stack
    cards: [
      card(47, 1, "col 1 (aside)", "left"),
      card(48, 2, "col 2 / nested row 1", "right"),
      card(49, 3, "col 2 / nested row 2", "right"),
    ],
    expectRows: 2,
    expect: {
      47: { col: 1, gridRow: "1 / -1" },            // lone side card → full-height column
      48: { col: 2, row: 1 },
      49: { col: 2, row: 2 },
    },
  },
  {
    name: "harmonics-pq (panel-overview-shell/harmonics-pq) — header lifted, r2/r3 rebased",
    templateRows: "repeat(2, minmax(0, 1fr))",
    cards: [                                        // card 23 (header) is a band → NOT passed here
      card(24, 2, "r2 left", "main"),
      card(25, 3, "r2 right", "right"),
      card(26, 4, "r3 left", "main"),
      card(27, 5, "r3 right", "right"),
    ],
    expectRows: 2,
    expect: {
      24: { col: 1, row: 1 },                       // r2 → grid row 1 (header rebased out)
      25: { col: 2, row: 1 },
      26: { col: 1, row: 2 },                       // r3 → grid row 2
      27: { col: 2, row: 2 },
    },
  },
  {
    name: "voltage-current (panel-overview-shell/voltage-current) — header lifted, 2x2",
    templateRows: "minmax(180px,1fr) minmax(240px,1fr)",
    cards: [                                        // card 18 (header) is a band
      card(19, 2, "r1 c1", "main"),
      card(20, 3, "r1 c2", "main"),
      card(21, 4, "r2 c1", "main"),
      card(22, 5, "r2 c2", "main"),
    ],
    expectRows: 2,
    expect: {
      19: { col: 1, row: 1 }, 20: { col: 2, row: 1 },
      21: { col: 1, row: 2 }, 22: { col: 2, row: 2 },
    },
  },
  {
    name: "energy-power (panel-overview-shell/energy-power) — no band, 2x2",
    templateRows: "minmax(300px, 340px) minmax(300px, 340px)",
    cards: [
      card(14, 1, "r1 c1", "main"), card(16, 2, "r1 c2", "main"),
      card(15, 3, "r2 c1", "main"), card(17, 4, "r2 c2", "main"),
    ],
    expectRows: 2,
    expect: {
      14: { col: 1, row: 1 }, 16: { col: 2, row: 1 },
      15: { col: 1, row: 2 }, 17: { col: 2, row: 2 },
    },
  },
  {
    name: "energy-distribution (panel-overview-shell/energy-distribution) — 2 cards, 1 row, no scroll",
    templateRows: "",
    cards: [ card(12, 1, "col 1", "left"), card(13, 2, "col 2", "right") ],
    expectRows: 1,
    expect: { 12: { col: 1 }, 13: { col: 2 } },
  },
  {
    name: "8-card panel RTM (panel-overview-shell/real-time-monitoring) — empty cells auto-stack, UNCHANGED",
    templateRows: "",                               // page declares no row tracks; all 8 cells are empty in the catalog
    cards: [
      card(7, 1, "", "left"), card(5, 2, "", "left"), card(160, 3, "", "left"), card(6, 4, "", "left"),
      card(8, 5, "", "right"), card(9, 6, "", "right"), card(10, 7, "", "right"), card(11, 8, "", "right"),
    ],
    expectRows: 8,
    expect: {
      7: { col: 1, row: 1, gridRow: "1" }, 5: { col: 1, row: 2, gridRow: "2" },
      160: { col: 1, row: 3, gridRow: "3" }, 6: { col: 1, row: 4, gridRow: "4" },
      8: { col: 1, row: 5, gridRow: "5" }, 9: { col: 1, row: 6, gridRow: "6" },
      10: { col: 1, row: 7, gridRow: "7" }, 11: { col: 1, row: 8, gridRow: "8" },
    },
  },
  {
    name: "individual energy-power (individual-feeder-meter-shell/energy-power) — '(or full)' annotation must NOT full-bleed",
    templateRows: "minmax(0, 1fr) minmax(0, 1fr)",  // exact catalog cells 39/40/41/42
    cards: [
      card(39, 1, "row 1 / col 1", "left"), card(40, 2, "row 1 / col 2", "right"),
      card(41, 3, "row 2 / col 1", "left"), card(42, 4, "row 2 / col 2 (or full)", "right"),
    ],
    expectRows: 2,
    expect: {
      39: { col: 1, row: 1 }, 40: { col: 2, row: 1 }, 41: { col: 1, row: 2 },
      42: { col: 2, row: 2, gridColumn: "2" },        // THE BUG: "full" stretched 42 to "1 / -1" over card 41 (col1,row2)
    },
  },
  {
    name: "UPS output-load-capacity (ups-asset-dashboard/output-load-capacity) — 'col 2 / full' = full-HEIGHT rail, not full-width",
    templateRows: "",                               // exact catalog cells 57/58/59
    cards: [
      card(57, 1, "col 1 / row 1", "left"), card(58, 2, "col 1 / row 2", "left"), card(59, 3, "col 2 / full", "main"),
    ],
    expectRows: 2,
    expect: {
      57: { col: 1, row: 1 }, 58: { col: 1, row: 2 },
      59: { col: 2, gridRow: "1 / -1" },              // 'col 2 / full' → col 2 side-rail spanning both rows (lone-rule)
    },
  },
  {
    name: "DG fuel-efficiency (diesel-generator-asset-dashboard/fuel-efficiency) — DUPLICATE authored cells de-collide, no overlap",
    templateRows: "",                               // exact catalog: cards 63 & 64 BOTH authored '1 / 1'
    cards: [ card(63, 1, "1 / 1", "left"), card(64, 2, "1 / 1", "left"), card(65, 3, "2 / 1", "right") ],
    expectRows: 3,
    expect: {                                        // 64 bumped off the taken (c1,r1) → r2; 65's (c1,r2) taken → r3
      63: { col: 1, row: 1, gridRow: "1" }, 64: { col: 1, row: 2, gridRow: "2" }, 65: { col: 1, row: 3, gridRow: "3" },
    },
  },
  {
    name: "individual overview (individual-feeder-meter-shell/overview) — nested left/right stack de-collides to one column",
    templateRows: "minmax(0, 1fr)",                 // exact catalog cells 30-34 (col-1 card has NULL card_id → not emitted)
    cards: [
      card(30, 4, "col 2 / stack row 2 / right", "right"), card(31, 5, "col 2 / stack row 3 / left", "right"),
      card(32, 6, "col 2 / stack row 3 / right", "right"), card(33, 7, "col 2 / stack row 4 / left", "right"),
      card(34, 8, "col 2 / stack row 4 / right", "right"),
    ],
    expectRows: 5,
    expect: {                                        // header rebased (min row 2 → r1); 31/32 & 33/34 pairs de-collide down
      30: { col: 2, row: 1 }, 31: { col: 2, row: 2 }, 32: { col: 2, row: 3 },
      33: { col: 2, row: 4 }, 34: { col: 2, row: 5 },
    },
  },
  {
    name: "overview-split (air-dryer/overview-split) — PROSE grid_template_rows is rejected, equal rows derived",
    templateRows: "three flex layers: tiles shrink-0 / chart flex-[3] / table flex-[2]",  // NOT a CSS track list
    cards: [
      card(90, 1, "layer 1 (shrink-0)", "main"), card(91, 2, "layer 2 (flex-[3])", "main"), card(92, 3, "layer 3 (flex-[2])", "main"),
    ],
    expectRows: 3,                                   // countRowTracks(plan.rows) must be 3 (derived), NOT 11 (prose words)
    expect: { 90: { col: 1, row: 1 }, 91: { col: 1, row: 2 }, 92: { col: 1, row: 3 } },
  },
];

// BAND VOCAB — which page_layout_cards.region values lift into the full-width top band (above the grid). DB-driven
// (vocab.band_regions); 'banner' (transformers 'intent banner above grid') MUST lift, footer/main/left/right MUST NOT.
const bandExpect = [
  ["strip", true], ["header", true], ["top", true], ["banner", true], ["STRIP", true],
  ["main", false], ["left", false], ["right", false], ["footer", false], ["grid", false], ["", false], [null, false],
];

let failed = 0, total = 0;
const collisions = (seats) => {
  const seen = new Set(); const dups = [];
  for (const s of seats) { const k = `${s.col},${s.row}`; if (seen.has(k)) dups.push(k); seen.add(k); }
  return dups;
};

// SPAN-AWARE OCCUPANCY: expand a gridColumn/gridRow style value ("2", 2, "1 / -1", "1 / 3") into the tracks it
// occupies, then assert NO two cards share ANY (col,row) cell. The plain duplicate check above skips spanning cards —
// exactly how the DG-1 RTM bug hid (38 stretched "1 / -1" over 36's right half without a same-(col,row) duplicate).
const expand = (v, fallback, n) => {
  const s = String(v ?? fallback);
  const m = /^(\d+)\s*\/\s*(-?\d+)$/.exec(s);
  if (!m) return [Number(s)];
  const a = Number(m[1]); const b = m[2] === "-1" ? n + 1 : Number(m[2]);
  const out = []; for (let t = a; t < Math.max(b, a + 1); t++) out.push(t); return out;
};
const spanOverlaps = (plan) => {
  const nCols = Math.max(1, ...plan.seats.flatMap((s) => {
    const m = /^(\d+)\s*\/\s*(\d+)$/.exec(String(s.style.gridColumn ?? ""));
    return m ? [Number(m[2]) - 1, s.col] : [s.col];
  }));
  const seen = new Map(); const bad = [];
  for (const s of plan.seats)
    for (const c of expand(s.style.gridColumn, s.col, nCols))
      for (const r of expand(s.style.gridRow, s.row, plan.nRows)) {
        const k = `${c},${r}`;
        if (seen.has(k)) bad.push(`cards ${seen.get(k)}+${s.card_id} overlap at (col ${c}, row ${r})`);
        else seen.set(k, s.card_id);
      }
  return bad;
};

for (const tc of cases) {
  total++;
  const plan = planGrid(tc.cards, tc.templateRows);
  const seatById = Object.fromEntries(plan.seats.map((s) => [s.card_id, s]));
  const problems = [];

  // 1) no two NON-spanning cards share a (col,row) cell — the power-quality bug was 48 & 49 both at col2,row1.
  const nonSpan = plan.seats.filter((s) => s.style.gridRow !== "1 / -1" && s.style.gridColumn !== "1 / -1");
  const dup = collisions(nonSpan);
  if (dup.length) problems.push(`cell collision(s): ${dup.join("; ")}`);

  // 1b) SPAN-AWARE: no card's occupied cells (spans expanded) overlap another's — the DG-1 RTM bug was card 38
  //     lone-stretched to gridRow "1 / -1" over full-width card 36's (col 2, row 1) cell.
  for (const o of spanOverlaps(plan)) problems.push(o);

  // 2) declared/derived row tracks match the rows actually used (no implicit overflow row → no viewport scroll).
  const tracks = countRowTracks(plan.rows);
  if (tracks !== tc.expectRows) problems.push(`row tracks ${tracks} != expected ${tc.expectRows} (plan.nRows=${plan.nRows})`);
  if (plan.nRows !== tc.expectRows) problems.push(`plan.nRows ${plan.nRows} != expected ${tc.expectRows}`);

  // 3) each expected card lands at its expected column/row (or full-height span).
  for (const [id, want] of Object.entries(tc.expect)) {
    const s = seatById[id];
    if (!s) { problems.push(`card ${id} missing from plan`); continue; }
    if (want.col != null && s.col !== want.col) problems.push(`card ${id} col=${s.col} want ${want.col}`);
    if (want.row != null && s.row !== want.row) problems.push(`card ${id} row=${s.row} want ${want.row}`);
    if (want.gridRow != null && String(s.style.gridRow) !== want.gridRow)
      problems.push(`card ${id} gridRow=${s.style.gridRow} want ${want.gridRow}`);
    if (want.gridColumn != null && String(s.style.gridColumn) !== want.gridColumn)
      problems.push(`card ${id} gridColumn=${s.style.gridColumn} want ${want.gridColumn}`);
  }

  if (problems.length) { failed++; console.log(`FAIL  ${tc.name}`); for (const p of problems) console.log(`        - ${p}`); }
  else console.log(`ok    ${tc.name}  (${plan.nRows} rows, ${plan.seats.length} cards)`);
}

// BAND VOCAB assertions (DB-driven region → band). A regression here means a header/strip/banner card would seat INSIDE
// the grid (displacing a body card) instead of lifting into the top band.
{
  total++;
  const bad = bandExpect.filter(([r, want]) => isBand(r) !== want).map(([r, want]) => `isBand(${JSON.stringify(r)})=${isBand(r)} want ${want}`);
  if (bad.length) { failed++; console.log(`FAIL  band vocab (region → top band)`); for (const b of bad) console.log(`        - ${b}`); }
  else console.log(`ok    band vocab (region → top band)  (${bandExpect.length} regions, incl. 'banner' lift)`);
}

console.log("—".repeat(72));
if (failed) { console.log(`LAYOUT GATE: FAIL (${failed}/${total} cases)`); process.exit(1); }
console.log(`LAYOUT GATE: PASS (${total}/${total} cases — every page seats its cards by template cells into one bounded viewport)`);
