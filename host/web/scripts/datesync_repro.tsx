// scripts/datesync_repro.tsx — PAGE-LEVEL DATE-SYNC gate (no browser): render DateSyncProvider + two is_history
// CmdCards under jsdom, mock fetch, fire ONE card's onDateChange, assert BOTH cards re-fetch /api/frame (the
// page-level propagation contract) and the non-history card does NOT. Run: npx vite-node scripts/datesync_repro.tsx
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body><div id='root'></div></body></html>", { url: "http://localhost/" });
const g: any = globalThis;
g.window = dom.window; g.document = dom.window.document;
try { Object.defineProperty(g, "navigator", { value: dom.window.navigator, configurable: true }); } catch { /* node>=21 read-only navigator */ }
g.HTMLElement = dom.window.HTMLElement;
g.getComputedStyle = dom.window.getComputedStyle;
g.requestAnimationFrame = (cb: any) => setTimeout(cb, 0);

// mock fetch BEFORE importing the app modules — record every /api/frame body, return a distinct payload
const frameCalls: any[] = [];
(globalThis as any).fetch = async (url: any, opts: any) => {
  if (String(url).includes("/api/frame")) {
    const body = JSON.parse(opts?.body || "{}");
    frameCalls.push(body);
    return { ok: true, status: 200, json: async () => ({ ok: true, payload: { refetched: true, n: frameCalls.length } }) } as any;
  }
  return { ok: true, status: 200, json: async () => ({}) } as any;
};

async function main() {
  const React = (await import("react")).default;
  const { createRoot } = await import("react-dom/client");
  const { DateSyncProvider } = await import("../src/components/DateSync");
  const { CmdCard } = await import("../src/components/CmdCard");

  // three cards: two is_history (must BOTH re-fetch), one snapshot (must NOT)
  const mk = (id: number, isHistory: boolean) => ({
    card_id: id, render_card_id: id, title: `card-${id}`, is_history: isHistory,
    payload: { some: "payload" }, data_instructions: { consumer: { is_history: isHistory } },
    refetch: { render_card_id: id, asset_table: "t", asset_name: "A", member_scope: "outgoing", _default_payload: null },
    render: { verdict: "render" },
  } as any);

  const root = createRoot(document.getElementById("root")!);
  let fire: ((dw: any) => void) | null = null;

  // Grab card-1's onDateChange by intercepting renderCmd via a probe component: simplest = drive the shared context
  // directly through a probe INSIDE the provider (equivalent to a card's date control calling onDateChange).
  const { useDateSync } = await import("../src/components/DateSync");
  function Probe() {
    const { setWindow } = useDateSync();
    (fire as any) = setWindow;
    return null;
  }

  await new Promise<void>((res) => {
    root.render(
      React.createElement(DateSyncProvider, null,
        React.createElement(Probe),
        React.createElement(CmdCard, { card: mk(1, true) }),
        React.createElement(CmdCard, { card: mk(2, true) }),
        React.createElement(CmdCard, { card: mk(3, false) }),
      ),
    );
    setTimeout(res, 50);
  });

  if (!fire) { console.log("FAIL: no setWindow captured"); process.exit(1); }
  console.log(`before pick: /api/frame calls = ${frameCalls.length} (want 0 — no window yet)`);
  const before = frameCalls.length;

  // ONE date pick (as card-18's control would emit) → published to the shared window
  (fire as any)({ range: "last-7-days", sampling: "day" });
  await new Promise((r) => setTimeout(r, 100));

  const after = frameCalls.length - before;
  const ids = frameCalls.slice(before).map((b) => b?.refetch?.render_card_id).sort();
  console.log(`after ONE pick: ${after} /api/frame calls from cards [${ids}] (want 2 — both history cards, NOT the snapshot)`);
  const pass = before === 0 && after === 2 && ids.join(",") === "1,2";
  console.log(pass ? "DATESYNC GATE: PASS — one pick re-fetches EVERY history card, snapshot untouched" : "DATESYNC GATE: FAIL");
  process.exit(pass ? 0 : 1);
}
main().catch((e) => { console.log("FAIL:", e?.message || e); process.exit(1); });
