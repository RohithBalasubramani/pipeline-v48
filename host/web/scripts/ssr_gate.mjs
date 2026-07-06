// scripts/ssr_gate.mjs — STANDING SSR GATE [family H]. Renders EVERY card of EVERY served-response JSON given
// (glob patterns supported) through the REAL renderCmd path (registry → guards/shims → CMD_V2 components) with
// react-dom/server, exactly like ssr_repro but as a pass/fail gate:
//   FAIL (exit 1) on ANY card that THROWS, or that falls to the NULL renderCmd fallback while carrying a payload
//   (a payload-bearing card must render its real component — NULL means a registry hole, not an honest blank).
//   A card with NO payload may return null (honest placeholder) — reported but not a failure.
// Run: npm run ssr-gate -- '<glob-or-file>' [more...]   (quotes keep the glob for this script to expand)
import { renderToString } from "react-dom/server";
import { renderCmd } from "../src/cmd/registry";
import fs from "node:fs";
import path from "node:path";

// ── tiny dependency-free glob expansion (supports * and ? in the BASENAME; dirname taken literally) ────────────
function expand(arg) {
  if (!/[*?]/.test(arg)) return [arg];
  const dir = path.dirname(arg);
  const rx = new RegExp(
    "^" + path.basename(arg).replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$",
  );
  let names = [];
  try { names = fs.readdirSync(dir); } catch { return []; }
  return names.filter((n) => rx.test(n)).sort().map((n) => path.join(dir, n));
}

const files = process.argv.slice(2).flatMap(expand);
if (!files.length) {
  console.error("usage: npm run ssr-gate -- <response.json|glob> [more...]");
  process.exit(2);
}

let totFiles = 0, totCards = 0, totOk = 0, totThrow = 0, totNullWithPayload = 0, totNullNoPayload = 0;
const failures = [];   // {file, card_id, kind, msg}

for (const file of files) {
  let resp;
  try { resp = JSON.parse(fs.readFileSync(file, "utf8")); } catch (e) {
    failures.push({ file, card_id: null, kind: "UNREADABLE", msg: String(e?.message ?? e) });
    console.log(`${file}: UNREADABLE (${e?.message ?? e})`);
    continue;
  }
  totFiles++;
  const cards = resp.cards ?? [];
  let ok = 0, thrown = 0, nullP = 0, nullNP = 0;
  for (const card of cards) {
    totCards++;
    const hasPayload = card.payload != null;
    try {
      const node = renderCmd(card, null);
      if (node == null) {
        if (hasPayload) {
          nullP++; totNullWithPayload++;
          failures.push({ file, card_id: card.card_id, kind: "NULL-FALLBACK", msg: "renderCmd returned NULL for a payload-bearing card" });
        } else { nullNP++; totNullNoPayload++; }
        continue;
      }
      renderToString(node);
      ok++; totOk++;
    } catch (e) {
      thrown++; totThrow++;
      failures.push({ file, card_id: card.card_id, kind: "THROW", msg: String(e?.message ?? e) });
    }
  }
  const flag = thrown || nullP ? "FAIL" : "ok  ";
  console.log(`${flag} ${path.basename(file)}: ${cards.length} cards — ${ok} rendered, ${thrown} throw, ${nullP} null-with-payload, ${nullNP} null-no-payload`);
}

console.log("—".repeat(72));
console.log(`TOTAL: ${totFiles} files, ${totCards} cards — ${totOk} rendered OK, ${totThrow} THROW, ${totNullWithPayload} NULL-with-payload (failures), ${totNullNoPayload} null-no-payload (honest placeholders)`);
if (failures.length) {
  console.log("FAILURES:");
  for (const f of failures) console.log(`  ${f.file} card ${f.card_id}: ${f.kind} -> ${f.msg}`);
  process.exit(1);
}
console.log("SSR GATE: PASS (zero throws, zero payload-bearing null fallbacks)");
