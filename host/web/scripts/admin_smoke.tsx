// scripts/admin_smoke.tsx — ADMIN CONSOLE smoke: mounts the real <AdminApp/> in jsdom against the LIVE admin API
// (:8790), walks every section, and fails on any render throw / empty section / console.error. Run:
//     npx vite-node scripts/admin_smoke.tsx            (admin server must be up: python3 admin/server.py)
// The admin section imports NO CMD_V2 code, so none of client_repro's React-dedupe machinery is needed here.
import { JSDOM } from "jsdom";

const ADMIN_API = process.env.V48_ADMIN_API || "http://localhost:8790";

const dom = new JSDOM(`<!doctype html><html><body><div id="root"></div></body></html>`, {
  url: "http://localhost:5188/admin",
  pretendToBeVisual: true,
});
(globalThis as any).window = dom.window;
(globalThis as any).document = dom.window.document;
Object.defineProperty(globalThis, "navigator", { value: dom.window.navigator, configurable: true });
(globalThis as any).HTMLElement = dom.window.HTMLElement;
(globalThis as any).PopStateEvent = dom.window.PopStateEvent;

// relative /admin/api/* → the live server (node's own fetch; jsdom doesn't ship one)
const realFetch = globalThis.fetch.bind(globalThis);
const proxiedFetch: typeof fetch = (input: any, init?: any) =>
  realFetch(typeof input === "string" && input.startsWith("/") ? `${ADMIN_API}${input}` : input, init);
(globalThis as any).fetch = proxiedFetch;
(dom.window as any).fetch = proxiedFetch;

const consoleErrors: string[] = [];
const origErr = console.error;
console.error = (...a: any[]) => {
  const s = a.map(String).join(" ");
  if (!/not wrapped in act|unique "key" prop/.test(s)) consoleErrors.push(s.slice(0, 200));
  origErr(...a);
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const { createRoot } = await import("react-dom/client");
  const React = (await import("react")).default;
  const { AdminApp } = await import("../src/admin/AdminApp");
  const { navigate } = await import("../src/admin/router");

  const root = createRoot(document.getElementById("root")!);
  root.render(React.createElement(AdminApp));
  await sleep(2500);

  const failures: string[] = [];
  const body = () => document.body.textContent || "";

  if (!body().includes("V48 ADMIN")) failures.push("shell: header missing");
  const runIds = body().match(/r_[0-9a-f]{10}/g) || [];
  if (!runIds.length) failures.push("runs: no run ids rendered");
  console.log(`[runs] rendered, ${new Set(runIds).size} distinct run ids visible`);

  // every section must render non-empty and without a crash banner
  const SECTIONS = ["explorer", "coverage", "latency", "failures", "ai", "sql", "assets", "validation", "search", "replay"];
  for (const s of SECTIONS) {
    navigate(s);
    await sleep(1800);
    const text = body();
    if (text.includes("Application error")) failures.push(`${s}: crash banner`);
    else if (text.replace(/V48 ADMIN.*?command center/s, "").trim().length < 40) failures.push(`${s}: empty`);
    else console.log(`[${s}] ok (${text.length} chars)`);
  }

  // trace viewer on a real run
  const rid = runIds[0];
  navigate(`trace/${rid}`);
  await sleep(2500);
  const t = body();
  for (const label of ["Prompt", "Layer 2", "Executor", "Renderer"]) {
    if (!t.includes(label)) failures.push(`trace: stage "${label}" missing`);
  }
  console.log(`[trace ${rid}] ok — stages present`);

  if (consoleErrors.length) failures.push(`console.error x${consoleErrors.length}: ${consoleErrors[0]}`);
  if (failures.length) {
    console.error("ADMIN SMOKE FAIL:\n  " + failures.join("\n  "));
    process.exit(1);
  }
  console.log("ADMIN SMOKE PASS");
  process.exit(0);
}

main().catch((e) => { console.error("harness error:", e); process.exit(1); });
