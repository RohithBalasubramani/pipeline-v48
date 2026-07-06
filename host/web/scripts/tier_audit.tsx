// scripts/tier_audit.tsx — TIER-REORDER AUDIT harness (Lane C, 2026-07-06). registry.tsx now serves FILL before
// COMPONENTS; for every card id registered in BOTH tiers this renders each served payload BOTH ways —
//   A. the FILL path (what the app serves now):        FILL[id](guardPayload(forceBlank(payload)), null, noop)
//   B. the direct component spread (the old winner):   <COMPONENTS[id] {...unwrap(guardPayload(forceBlank(payload)))}/>
// — and diffs the VISIBLE TEXT. A fill that renders LESS data than the spread (numbers/labels present in B, missing
// in A) is a regression; extra tokens in A are usually the date-control chrome only the fill can wire (a JSON payload
// cannot carry onSamplingChange, so the picker never renders on the spread path).
//
//   npx vite-node scripts/tier_audit.tsx                        (defaults to <repo>/outputs/logs/response_*.json)
//   npx vite-node scripts/tier_audit.tsx <response.json> [...]  (explicit files)
//
// Pure renderToString (same env as ssr_repro.tsx). Reporting only — no exit-code gate; the standing gates stay
// ssr_gate.mjs + client_repro --gate.
import { renderToString } from "react-dom/server";
import React from "react";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { COMPONENTS } from "../src/cmd/components";
import { guardPayload } from "../src/cmd/guards";
import { unwrap, forceBlank } from "../src/cmd/registry";

// same loader rule as registry.tsx (single-level glob, m.CARDS)
const fillMods = import.meta.glob("../src/cmd/fill/*.tsx", { eager: true }) as Record<string, any>;
const FILL: Record<number, any> = {};
for (const m of Object.values(fillMods)) {
  for (const [id, fn] of Object.entries(m?.CARDS ?? {})) if (typeof fn === "function") FILL[Number(id)] = fn;
}

const strip = (html: string) =>
  html
    .replace(/<(style|script)[\s\S]*?<\/\1>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;|&#160;/g, " ")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();

// multiset difference a − b over whitespace tokens
function tokenDiff(a: string[], b: string[]): string[] {
  const counts = new Map<string, number>();
  for (const t of b) counts.set(t, (counts.get(t) ?? 0) + 1);
  const out: string[] = [];
  for (const t of a) {
    const c = counts.get(t) ?? 0;
    if (c > 0) counts.set(t, c - 1);
    else out.push(t);
  }
  return out;
}
const hasDigit = (t: string) => /\d/.test(t);
const controls = (html: string) => ({
  select: (html.match(/<select/g) ?? []).length,
  button: (html.match(/<button/g) ?? []).length,
  input: (html.match(/<input/g) ?? []).length,
});

async function main() {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const args = process.argv.slice(2).filter((a) => a !== "--");
  const files = args.length
    ? args
    : fs
        .readdirSync(path.resolve(here, "../../../outputs/logs"))
        .filter((n) => /^response_.*\.json$/.test(n))
        .sort()
        .map((n) => path.resolve(here, "../../../outputs/logs", n));

  // silence render-time console noise (useLayoutEffect warnings etc.) — throws are what we report
  const origErr = console.error;
  console.error = () => {};

  let pairs = 0, regressions = 0;
  for (const file of files) {
    let resp: any;
    try { resp = JSON.parse(fs.readFileSync(file, "utf8")); } catch { continue; }
    for (const card of resp.cards ?? []) {
      const id = card.render_card_id ?? card.card_id;
      if (!FILL[id] || !COMPONENTS[id]) continue;
      pairs++;
      const rv = card.render || {};
      const prep = () => {
        const fb = forceBlank(card.payload, rv.suppress_default_leaves);
        return guardPayload(fb == null ? {} : fb);
      };
      let fillHtml = "", compHtml = "", fillErr = "", compErr = "";
      try { fillHtml = renderToString(React.createElement(React.Fragment, null, FILL[id](prep(), null, () => {}, null))); }
      catch (e: any) { fillErr = String(e?.message ?? e); }
      try { compHtml = renderToString(React.createElement(COMPONENTS[id], unwrap(prep()))); }
      catch (e: any) { compErr = String(e?.message ?? e); }

      const fillT = strip(fillHtml).split(" ").filter(Boolean);
      const compT = strip(compHtml).split(" ").filter(Boolean);
      const missing = tokenDiff(compT, fillT); // in spread, NOT in fill  → potential data regression
      const extra = tokenDiff(fillT, compT);   // in fill, NOT in spread  → usually date-control chrome
      const missingData = missing.filter(hasDigit);
      const fc = controls(fillHtml), cc = controls(compHtml);

      const flag = compErr && !fillErr ? "FILL-SAVES" : fillErr ? "FILL-THROWS" : missingData.length ? "CHECK" : "ok";
      if (flag === "CHECK" || flag === "FILL-THROWS") regressions++;
      console.log(
        `${flag.padEnd(11)} card ${String(id).padStart(3)} ${path.basename(file)} | fill ${fillHtml.length}ch comp ${compHtml.length}ch` +
        ` | missing ${missing.length} (data ${missingData.length}) extra ${extra.length}` +
        ` | ctl fill s${fc.select}/b${fc.button}/i${fc.input} comp s${cc.select}/b${cc.button}/i${cc.input}`,
      );
      if (fillErr) console.log(`    fill THROWS: ${fillErr}`);
      if (compErr) console.log(`    comp throws: ${compErr}`);
      if (missingData.length) console.log(`    missing-data sample: ${missingData.slice(0, 25).join(" ")}`);
      if (process.env.TIER_AUDIT_VERBOSE) {
        if (missing.length) console.log(`    missing all: ${missing.slice(0, 40).join(" ")}`);
        if (extra.length) console.log(`    extra all:   ${extra.slice(0, 40).join(" ")}`);
      }
    }
  }
  console.error = origErr;
  console.log("—".repeat(72));
  console.log(`tier audit: ${pairs} double-registered card renders compared, ${regressions} flagged (CHECK/FILL-THROWS)`);
}
main();
