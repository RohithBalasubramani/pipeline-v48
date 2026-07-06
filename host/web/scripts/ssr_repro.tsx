// scripts/ssr_repro.tsx — server-side repro harness: render the EXACT served card payloads through the real
// renderCmd path (registry + CMD_V2 components) and print the throw each card produces (the Boundary masks these
// in the browser as an honest-looking blank). Run: npx vite-node scripts/ssr_repro.tsx <response.json> [card_id...]
// SSR_GREP="some text" additionally reports whether each card's rendered HTML CONTAINS that text (e.g. proving a
// card's data_note disclosure is actually visible in the markup, not just non-crashing). [B1 residual 'fe']
import { renderToString } from "react-dom/server";
import { renderCmd } from "../src/cmd/registry";
import fs from "node:fs";

const [file, ...ids] = process.argv.slice(2);
const resp = JSON.parse(fs.readFileSync(file, "utf8"));
const want = new Set(ids.map(Number));
for (const card of resp.cards ?? []) {
  if (want.size && !want.has(Number(card.card_id))) continue;
  let out = "";
  try {
    const node = renderCmd(card, null);
    if (node == null) { console.log(`card ${card.card_id}: renderCmd returned NULL (falls to CmdCard placeholder)`); continue; }
    out = renderToString(node as any);
    const grep = process.env.SSR_GREP;
    const hit = grep ? (out.includes(grep) ? ` | GREP HIT: ${JSON.stringify(grep.slice(0, 60))}` : ` | grep miss`) : "";
    console.log(`card ${card.card_id}: rendered OK (${out.length} chars)${hit}`);
  } catch (e: any) {
    console.log(`card ${card.card_id}: THROWS -> ${e?.message ?? e}`);
    const st = String(e?.stack ?? "").split("\n").slice(1, 4).join(" | ");
    console.log(`   stack: ${st}`);
  }
}
