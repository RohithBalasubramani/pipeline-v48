// scripts/client_repro.tsx — CLIENT-MODE render harness: mounts served cards through the real renderCmd with
// react-dom/client inside jsdom, flushing EFFECTS (the phase renderToString skips — chart draw/measure/observer
// crashes only reproduce here). Complements ssr_repro.tsx / ssr_gate.mjs. TWO MODES:
//
//   DEBUG (single literal file, optional card ids — the original repro):
//     npx vite-node scripts/client_repro.tsx <abs response.json> [card_id...]
//     verbose per-card output, every console.error echoed + reported.
//
//   GATE (standing check — glob patterns, many files, per-file summary, pass/fail exit):
//     npm run client-gate                       (defaults to <repo>/outputs/logs/response_*.json)
//     npm run client-gate -- '<glob-or-file>' [more...]
//     FAIL (exit 1) on ANY card that THROWS during client mount/effects (sync throw, onUncaughtError, window
//     error), OR any NaN-ATTRIBUTE console error (React's "Received NaN for the `y1` attribute…" family — NaN
//     SVG geometry shipped to the DOM) on a card that carries a payload. NaN-attr on a NO-payload card and other
//     console noise (act/key warnings) are reported as warnings, never failures. Mirrors ssr_gate.mjs reporting.
import { JSDOM } from "jsdom";
import NodeModule, { createRequire } from "node:module";

// ── ENV FIX 1 — ONE React (browser parity). The Vite build dedupes react/react-dom/scheduler onto host/web's copies
// (vite.config resolve.dedupe + alias); vite-node EXTERNALIZES node_modules deps, so a hook-calling package under
// CMD_V2/node_modules (its-fine, @react-three/fiber, react-redux, framer-motion, …) natively resolves
// /home/rohith/CMD_V2/node_modules/react — a SECOND React whose hooks dispatcher is null under host react-dom
// ("Cannot read properties of null (reading 'useContext')" — HARNESS-ONLY, the browser never sees it). Mirror the
// build's dedupe at the node loader: any react/react-dom/scheduler request whose importer lives under CMD_V2 resolves
// from host/web instead. node>=22.15 sync hooks cover BOTH require() and import.
const REACT_IDS = /^(react|react-dom|scheduler)([/]|$)/;
const HOOK_DEBUG = !!process.env.CLIENT_REPRO_HOOK_DEBUG;
if (HOOK_DEBUG) console.log("[hook] import.meta.url =", import.meta.url);
const registerHooks = (NodeModule as any).registerHooks;
if (typeof registerHooks === "function") {
  registerHooks({
    resolve(specifier: string, context: any, nextResolve: any) {
      // bare-name requests from a CMD_V2 importer → resolve as if from host/web/scripts (fast path)
      if (REACT_IDS.test(specifier) && String(context?.parentURL ?? "").includes("/CMD_V2/")) {
        return nextResolve(specifier, { ...context, parentURL: import.meta.url });
      }
      // RESULT rewrite — the catch-all. vite-node reaches CMD_V2's react through several shapes this hook can't
      // pattern-match on the specifier alone (externalizer imports the RESOLVED ABSOLUTE PATH; an inlined CJS wrapper
      // requires './cjs/react.development.js' relatively). Whatever the route: a resolution landing inside CMD_V2's
      // react / react-dom / scheduler package is swapped for the SAME FILE under host/web (identical package layout,
      // react 19.2.4 → 19.2.7) — ONE dispatcher, exactly like the browser build's resolve.dedupe.
      const r = nextResolve(specifier, context);
      const leak = String(r?.url ?? "").match(/CMD_V2\/node_modules\/((?:react|react-dom|scheduler)\/.*)/);
      if (leak) {
        const host = new URL("../node_modules/" + leak[1], import.meta.url).href;
        if (HOOK_DEBUG) console.log("[hook] rewrite", String(r.url).slice(-60), "->", host.slice(-60));
        return { ...r, url: host };
      }
      return r;
    },
  });
} else if (HOOK_DEBUG) console.log("[hook] registerHooks unavailable");

// ── ENV FIX 2 — browsers NEVER throw on an invalid CSS value (CSSOM contract: invalid → declaration ignored).
// jsdom's css-values parsePropertyValue/resolveCalc parse with css-tree in throwing mode, so an honest-blank leaf
// reaching a style template (`calc(—% + 4px)` — FillBar badge left; `clamp(16px, —%, …)` — HealthSummaryPanel band
// marker) crashes the HARNESS where the real browser silently drops the declaration and renders the component's
// dashed text honestly. Wrap the parse in the browser's own ignore-on-invalid behavior; values that parse are
// untouched. (jsdom property modules call these through the `parsers.` namespace, so patching exports is effective.)
try {
  const cssValues = createRequire(import.meta.url)("jsdom/lib/jsdom/living/css/helpers/css-values.js");
  for (const fn of ["parsePropertyValue", "resolveCalc"]) {
    const orig = cssValues[fn];
    if (typeof orig === "function") {
      cssValues[fn] = (...a: any[]) => {
        try { return orig(...a); } catch { return undefined; }
      };
    }
  }
} catch { /* jsdom internals moved — css parse throws would then surface in the gate output */ }

const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { pretendToBeVisual: true });
const g: any = globalThis;
g.window = dom.window; g.document = dom.window.document;
try { Object.defineProperty(g, "navigator", { value: dom.window.navigator, configurable: true }); } catch { /* node>=21 read-only navigator */ }
g.HTMLElement = dom.window.HTMLElement; g.SVGElement = dom.window.SVGElement; g.Element = dom.window.Element;
g.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
// bare window globals browser libs reference without the window. prefix (react-use-measure reads `screen`)
for (const k of ["screen", "location", "history", "Node", "Event", "CustomEvent", "MouseEvent", "PointerEvent", "KeyboardEvent", "MutationObserver", "IntersectionObserver", "DOMRect"]) {
  if (g[k] === undefined && (dom.window as any)[k] !== undefined) g[k] = (dom.window as any)[k];
}
g.requestAnimationFrame = (cb: any) => setTimeout(() => cb(Date.now()), 0);
g.cancelAnimationFrame = (id: any) => clearTimeout(id);
// ResizeObserver that actually FIRES with a real-ish size — the browser-only chart-draw effects gate on size>0,
// so a silent stub never exercises them (the exact blind spot this harness exists to close).
g.window.ResizeObserver = class {
  cb: any; constructor(cb: any) { this.cb = cb; }
  observe(t: any) { setTimeout(() => this.cb([{ target: t, contentRect: { width: 800, height: 400, top: 0, left: 0, right: 800, bottom: 400, x: 0, y: 0 } }], this), 0); }
  unobserve() {} disconnect() {}
};
g.ResizeObserver = g.window.ResizeObserver;
const rect = { width: 800, height: 400, top: 0, left: 0, right: 800, bottom: 400, x: 0, y: 0, toJSON() { return this; } };
(dom.window.Element.prototype as any).getBoundingClientRect = () => ({ ...rect });
Object.defineProperty(dom.window.HTMLElement.prototype, "offsetWidth", { get: () => 800, configurable: true });
Object.defineProperty(dom.window.HTMLElement.prototype, "offsetHeight", { get: () => 400, configurable: true });
Object.defineProperty(dom.window.HTMLElement.prototype, "clientWidth", { get: () => 800, configurable: true });
Object.defineProperty(dom.window.HTMLElement.prototype, "clientHeight", { get: () => 400, configurable: true });
if (!g.window.matchMedia) g.window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });
g.matchMedia = g.window.matchMedia;
// SVG measure APIs charts touch during effects
for (const k of ["getBBox", "getComputedTextLength", "getTotalLength"]) {
  (dom.window.SVGElement.prototype as any)[k] = (dom.window.SVGElement.prototype as any)[k] || (() => (k === "getBBox" ? { x: 0, y: 0, width: 100, height: 20 } : 100));
}
(dom.window.HTMLCanvasElement.prototype as any).getContext = () => null;

// ── per-card error sinks (swapped per render) ────────────────────────────────────────────────────────────────
const sink = { throws: [] as string[], consoleErrs: [] as string[] };
dom.window.addEventListener("error", (e: any) => sink.throws.push(String(e?.error?.stack ?? e?.message ?? e)));
// an async rejection during effects (e.g. a lazy-chunk load) belongs to the CURRENT card, not a harness crash
process.on("unhandledRejection", (e: any) => sink.throws.push(String(e?.stack ?? e?.message ?? e)));

// React's NaN-attribute error family — "Received NaN for the `y1` attribute…" / "<rect> attribute height:
// Expected length, NaN" — i.e. NaN geometry actually shipped to the DOM.
const isNanAttr = (s: string) => /NaN/.test(s) && /attribut/i.test(s);
// jsdom has NO WebGL — three.js' WebGLRenderer constructor necessarily throws for the asset_3d viewer cards. That is
// an environment CAPABILITY limit (the browser has GL and renders these cards; SSR gate covers their markup), not a
// payload/render bug — gate mode reports it as warn-only. Matched EXACTLY on three's context-creation error so any
// other throw in the 3D path still fails the gate.
const isEnvLimit = (s: string) => /Error creating WebGL context/i.test(s);
const STACK_FRAMES = Number(process.env.CLIENT_REPRO_STACK || 3); // debug knob: CLIENT_REPRO_STACK=30 for full stacks
if (STACK_FRAMES > 3) Error.stackTraceLimit = STACK_FRAMES + 10;
const head = (s: any, n = 200) => String(s ?? "").split("\n")[0].slice(0, n);
const stackHead = (s: any) =>
  String(s ?? "").split("\n").slice(1, 1 + STACK_FRAMES).map((x) => x.trim()).join(" | ").slice(0, STACK_FRAMES > 3 ? 40000 : 400);

// ── tiny dependency-free glob expansion (supports * and ? in the BASENAME; dirname taken literally) ──────────
function expand(fs: any, path: any, arg: string): string[] {
  if (!/[*?]/.test(arg)) return [arg];
  const dir = path.dirname(arg);
  const rx = new RegExp(
    "^" + path.basename(arg).replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$",
  );
  let names: string[] = [];
  try { names = fs.readdirSync(dir); } catch { return []; }
  return names.filter((n) => rx.test(n)).sort().map((n) => path.join(dir, n));
}

type CardResult = { committed: number; throws: string[]; nanAttrs: string[]; otherErrs: string[] };

async function main() {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const { fileURLToPath } = await import("node:url");
  const React = (await import("react")).default;
  const { createRoot } = await import("react-dom/client");
  const { flushSync } = await import("react-dom");
  const { renderCmd } = await import("../src/cmd/registry");

  const rawArgs = process.argv.slice(2).filter((a) => a !== "--");
  const gateFlag = rawArgs.includes("--gate");
  const args = rawArgs.filter((a) => a !== "--gate");
  const hasGlob = args.some((a) => /[*?]/.test(a));
  const fileish = (a: string) => /[/\\]|\.json$/i.test(a) || /[*?]/.test(a);
  const fileArgs = args.filter(fileish);
  const gate = gateFlag || hasGlob || fileArgs.length > 1;

  const origConsoleError = console.error;
  console.error = (...a: any[]) => {
    sink.consoleErrs.push(a.map((x) => String(x?.stack ?? x)).join(" "));
    if (!gate) origConsoleError(...a); // gate mode: collect silently (failures re-printed in the report)
  };

  async function renderCard(card: any): Promise<CardResult> {
    sink.throws = []; sink.consoleErrs = [];
    const throws = sink.throws, consoleErrs = sink.consoleErrs;
    const el = dom.window.document.createElement("div");
    dom.window.document.body.appendChild(el);
    let committed = 0;
    try {
      const node = renderCmd(card, null);
      const root = createRoot(el, { onUncaughtError: (e: any) => throws.push(String(e?.stack ?? e)) } as any);
      flushSync(() => root.render(React.createElement(React.Fragment, null, node as any)));
      await new Promise((r) => setTimeout(r, 400)); // let effects + RO callbacks + rAF run
      committed = el.innerHTML.length;
      root.unmount();
    } catch (e: any) {
      throws.push(String(e?.stack ?? e?.message ?? e));
    }
    el.remove();
    return {
      committed,
      throws,
      nanAttrs: consoleErrs.filter(isNanAttr),
      otherErrs: consoleErrs.filter((s) => !isNanAttr(s)),
    };
  }

  // ── GATE MODE ───────────────────────────────────────────────────────────────────────────────────────────────
  if (gate) {
    const here = path.dirname(fileURLToPath(import.meta.url)); // <repo>/host/web/scripts
    const patterns = fileArgs.length ? fileArgs : [path.resolve(here, "../../../outputs/logs", "response_*.json")];
    const files = patterns.flatMap((p) => expand(fs, path, p));
    if (!files.length) { console.log("client-gate: no files matched", patterns.join(" ")); process.exit(2); }

    let totFiles = 0, totCards = 0, totClean = 0, totThrow = 0, totNan = 0, totWarnOnly = 0;
    const failures: { file: string; card_id: any; kind: string; msg: string; stack: string }[] = [];
    const warnings: { file: string; card_id: any; kind: string; msg: string }[] = [];

    for (const file of files) {
      let resp: any;
      try { resp = JSON.parse(fs.readFileSync(file, "utf8")); } catch (e: any) {
        failures.push({ file, card_id: null, kind: "UNREADABLE", msg: head(e?.message ?? e), stack: "" });
        console.log(`FAIL ${path.basename(file)}: UNREADABLE (${head(e?.message ?? e)})`);
        continue;
      }
      totFiles++;
      const cards = resp.cards ?? [];
      let clean = 0, thrown = 0, nan = 0, warn = 0;
      for (const card of cards) {
        totCards++;
        const hasPayload = card.payload != null;
        const r = await renderCard(card);
        // FAIL: any client throw; NaN-attribute console error on a payload-bearing card.
        // WARN-ONLY: the jsdom-has-no-WebGL throw (asset_3d viewer cards — env capability, not a render bug).
        const realThrows = r.throws.filter((s) => !isEnvLimit(s));
        const envThrows = r.throws.filter(isEnvLimit);
        if (envThrows.length) {
          warn++; totWarnOnly++;
          warnings.push({ file, card_id: card.card_id, kind: "WEBGL-ENV(no GL in jsdom)", msg: head(envThrows[0]) });
        }
        if (realThrows.length) {
          thrown++; totThrow++;
          failures.push({ file, card_id: card.card_id, kind: "THROW", msg: head(realThrows[0]), stack: stackHead(realThrows[0]) });
        }
        if (r.nanAttrs.length) {
          if (hasPayload) {
            nan++; totNan++;
            failures.push({ file, card_id: card.card_id, kind: "NAN-ATTR", msg: head(r.nanAttrs[0]), stack: stackHead(r.nanAttrs[0]) });
          } else {
            warn++; totWarnOnly++;
            warnings.push({ file, card_id: card.card_id, kind: "NAN-ATTR(no-payload)", msg: head(r.nanAttrs[0]) });
          }
        }
        if (!realThrows.length && !(hasPayload && r.nanAttrs.length)) { clean++; totClean++; }
      }
      const flag = thrown || nan ? "FAIL" : "ok  ";
      console.log(`${flag} ${path.basename(file)}: ${cards.length} cards — ${clean} clean, ${thrown} throw, ${nan} NaN-attr, ${warn} warn-only`);
    }

    console.log("—".repeat(72));
    console.log(`TOTAL: ${totFiles} files, ${totCards} cards — ${totClean} clean, ${totThrow} THROW, ${totNan} NaN-ATTR (failures), ${totWarnOnly} warn-only`);
    if (warnings.length) {
      console.log("WARNINGS (non-failing):");
      for (const w of warnings) console.log(`  ${path.basename(w.file)} card ${w.card_id}: ${w.kind} -> ${w.msg}`);
    }
    if (failures.length) {
      console.log("FAILURES:");
      for (const f of failures) {
        console.log(`  ${f.file} card ${f.card_id}: ${f.kind} -> ${f.msg}`);
        if (f.stack) console.log(`    stack: ${f.stack}`);
      }
      process.exit(1);
    }
    console.log("CLIENT GATE: PASS (zero client throws, zero payload-bearing NaN-attribute errors)");
    return;
  }

  // ── DEBUG MODE (original single-file repro) ─────────────────────────────────────────────────────────────────
  const [file, ...ids] = args;
  if (!file) { console.error("usage: vite-node scripts/client_repro.tsx <response.json> [card_id...] | --gate <glob...>"); process.exit(2); }
  const resp = JSON.parse(fs.readFileSync(file, "utf8"));
  const want = new Set(ids.map(Number));
  for (const card of resp.cards ?? []) {
    if (want.size && !want.has(Number(card.card_id))) continue;
    const r = await renderCard(card);
    const errs = [...r.throws, ...r.nanAttrs, ...r.otherErrs];
    if (!errs.length && r.committed === 0) errs.push("commit produced 0 chars (silent unmount)");
    if (errs.length) {
      console.log(`card ${card.card_id}: CLIENT-THROWS -> ${head(errs[0])}`);
      console.log(`   stack: ${stackHead(errs[0])}`);
    } else {
      console.log(`card ${card.card_id}: client render OK (committed ${r.committed} chars)`);
    }
  }
}
main().then(() => process.exit(process.exitCode ?? 0)).catch((e) => { console.error("harness error:", e?.stack ?? e?.message ?? e); process.exit(2); });
