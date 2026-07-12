// scripts/card_values.mjs — CORRECTNESS probe the SSR gate can't do: render each card to HTML and check whether the
// payload's REAL numeric values actually appear in the rendered text. Catches "renders all-dashes while the payload
// has data" (card 18 class), which the throw/null SSR gate passes. Heuristic, not a proof — a LOW hit-rate on a
// data-rich card is a strong smell to inspect. Run: npm run -s card-values -- <response.json> [more...]
import { renderToString } from "react-dom/server";
import { renderCmd } from "../src/cmd/registry";
import fs from "node:fs";

const files = process.argv.slice(2);

// distinctive numbers from a payload subtree: |v|>=1, keep 2 decimals; skip 0/near-0 and giant ids
function witnesses(o, acc = new Set(), depth = 0) {
  if (depth > 8 || o == null) return acc;
  if (typeof o === "number" || (typeof o === "string" && /^-?\d+(\.\d+)?$/.test(o))) {
    const n = Number(o);
    if (Number.isFinite(n) && Math.abs(n) >= 1 && Math.abs(n) < 1e12) acc.add(Math.abs(n));
    return acc;
  }
  if (Array.isArray(o)) { for (const v of o.slice(0, 40)) witnesses(v, acc, depth + 1); return acc; }
  if (typeof o === "object") { for (const v of Object.values(o)) witnesses(v, acc, depth + 1); return acc; }
  return acc;
}
// forms a rendered number might take: plain, comma-grouped, rounded 0/1/2 dp
function forms(n) {
  const s = new Set();
  for (const d of [0, 1, 2]) {
    const r = n.toFixed(d);
    s.add(r);
    s.add(Number(r).toLocaleString("en-IN"));
    s.add(Number(r).toLocaleString("en-US"));
  }
  s.add(String(Math.round(n)));
  return [...s];
}

for (const file of files) {
  let resp;
  try { resp = JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) { console.log(`${file}: UNREADABLE`); continue; }
  console.log(`\n=== ${file.split("/").pop()} ===`);
  for (const card of resp.cards ?? []) {
    const id = card.render_card_id ?? card.card_id;
    let html = "";
    try { const node = renderCmd(card, null); html = node == null ? "" : renderToString(node); }
    catch (e) { console.log(`  card ${id}: THROW ${String(e?.message ?? e).slice(0, 80)}`); continue; }
    const text = html.replace(/<[^>]*>/g, " ").replace(/&[a-z]+;/g, " ");
    const dashes = (text.match(/—/g) || []).length;
    const w = [...witnesses(card.payload)].filter((n) => n >= 5);   // ≥5 = a "real reading", not a count of 1-2
    let found = 0;
    for (const n of w) if (forms(n).some((f) => text.includes(f))) found++;
    const rate = w.length ? Math.round((found / w.length) * 100) : -1;
    const verdict = w.length >= 6 && rate <= 25 ? "  ⚠ LIKELY-BLANK" : (rate >= 0 && rate < 50 && w.length >= 4 ? "  ? low" : "");
    console.log(`  card ${String(id).padStart(3)}: witnesses=${String(w.length).padStart(3)} shown=${String(found).padStart(3)} (${rate}%)  dashes=${dashes}  htmlLen=${html.length}${verdict}`);
  }
}
