import React from "react";
import { COMPONENTS } from "./components";
import { COMPOSE } from "./compose";

// CARD_ID-KEYED REGISTRY. Three tiers, tried in order by render_card_id (the swap target if Layer 2 swapped, else the
// card itself) — so a swapped-in card from another page renders by its OWN identity:
//   1. FILL[id]  — per-page mapper-fill module (cmd/fill/<page>.tsx): uses the LIVE ems_backend frame via the card's
//                  OWN CMD V2 mapper/builder. The primary path (live + date-navigable data).
//   2. COMPOSE[id] — bespoke glue for stacked cards (no live frame; seed payload).
//   3. COMPONENTS[id] — generic <Component {...unwrap(payload)}> from the seed payload.
// a fill fn gets the card's payload (exact_metadata seed), the live frame, and onDateChange — which the fn wires to the
// card's OWN CMD V2 date control so changing the date re-fetches that card's frame. (Older fills ignore the 3rd arg.)
// `pageFrame` = the page's LIVE frame (frames[page_endpoint]). A few cards are bound by Layer 2 to a history endpoint
// (buckets shape) but their CMD V2 fill reads the LIVE aggregate (widgets) shape — they fall back to pageFrame.
type RenderFn = (payload: any, frame?: any, onDateChange?: (dw: any) => void, pageFrame?: any) => React.ReactNode;

// each fill module exports `CARDS: Record<card_id, (payload, frame) => ReactNode>`
const fillMods = import.meta.glob("./fill/*.tsx", { eager: true }) as Record<string, any>;
const FILL: Record<number, RenderFn> = {};
for (const [path, m] of Object.entries(fillMods)) {
  const cards = m?.CARDS;
  if (cards && typeof cards === "object") {
    for (const [id, fn] of Object.entries(cards)) {
      if (typeof fn === "function") {
        if (FILL[Number(id)]) console.warn(`[registry] duplicate fill for card ${id} (${path})`);
        FILL[Number(id)] = fn as RenderFn;
      }
    }
  }
}

// "OPEN THE BOX" — the seed payload wraps the real props one level down under a single key (+ a throwaway `variant`).
// Spread the inner AND re-attach it under its key so both spread-consumers and named-prop consumers are satisfied.
function unwrap(payload: any): any {
  if (!payload || typeof payload !== "object") return payload;
  const keys = Object.keys(payload).filter((k) => k !== "variant");
  if (keys.length === 1) {
    const inner = payload[keys[0]];
    if (inner && typeof inner === "object" && !Array.isArray(inner)) return { ...inner, [keys[0]]: inner };
  }
  const { variant, ...rest } = payload;
  return rest;
}

// ── NO-SEED-LEAK force-blank [VC-01/02] ──────────────────────────────────────────────────────────────────────────
// Split a dotted/bracketed path ('config.rows[2].value') into segments so a leaf can be force-blanked in the payload.
function segs(path: string): (string | number)[] {
  const out: (string | number)[] = [];
  for (const m of path.matchAll(/([^.[\]]+)|\[(\d+)\]/g)) out.push(m[2] !== undefined ? Number(m[2]) : m[1]);
  return out;
}
// Return a DEEP-CLONED payload with each `paths` leaf set to null. Defensive: the host already blanks these server-side,
// but the FE re-asserts it so a numeric that equals its seed with no live provenance can NEVER slip through. Never
// mutates the source payload.
function forceBlank(payload: any, paths?: string[]): any {
  if (!paths || !paths.length || !payload || typeof payload !== "object") return payload;
  let clone: any;
  try { clone = structuredClone(payload); } catch { clone = JSON.parse(JSON.stringify(payload)); }
  for (const p of paths) {
    const s = segs(p);
    let cur = clone;
    let ok = true;
    for (let i = 0; i < s.length - 1; i++) { if (cur == null) { ok = false; break; } cur = cur[s[i]]; }
    if (ok && cur != null && typeof cur === "object") cur[s[s.length - 1]] = null;
  }
  return clone;
}

// The honest-blank placeholder a card renders when the render-guarantee verdict is honest_blank (real data gap): the
// card's own frame with the machine reason — NOT a fabricated value, NOT a white screen. [contract: honest blank+reason]
function HonestBlank({ title, reason }: { title?: string; reason?: string | null }): React.ReactNode {
  return (
    <div className="placeholder" style={{ height: "100%", minHeight: 0 }}>
      <div className="big">—</div>
      <div>{title || "no live data"}</div>
      {reason ? <div className="k">{reason}</div> : null}
    </div>
  );
}

/** Render a pipeline card with its REAL CMD V2 component. `frame` = the live ems_backend frame for this card's endpoint
 *  (frames[card.endpoint]); a fill module maps it via the card's own CMD V2 mapper. null → caller shows the placeholder.
 *  The render-guarantee verdict (card.render) is OBEYED: a honest_blank verdict short-circuits to an honest reason card
 *  (never a seed), and suppress_default_leaves are force-blanked in the payload before it reaches the component. */
export function renderCmd(
  card: { card_id: number; render_card_id?: number; payload: any; title?: string; render?: any } | null | undefined,
  frame?: any,
  onDateChange?: (dw: any) => void,
  pageFrame?: any,
): React.ReactNode {
  if (!card) return null;
  const rv = card.render || {};
  // HONEST-BLANK verdict (a real data gap L3 already decided) → render the reason, never a stale seed. Only short-circuit
  // when there is NO live frame to fill from; with a live frame the fill mapper draws the real values.
  if (rv.verdict === "honest_blank" && !frame) {
    return <HonestBlank title={card.title} reason={rv.reason || rv.coverage_note} />;
  }
  const payload = forceBlank(card.payload, rv.suppress_default_leaves);  // NO-SEED-LEAK: blank unprovenanced leaves
  const id = card.render_card_id ?? card.card_id;
  if (FILL[id]) return FILL[id](payload, frame, onDateChange, pageFrame);  // live mapper-fill (primary)
  const glue = COMPOSE[id];
  if (glue) return glue(payload, frame);                       // bespoke glue (seed)
  const Comp = COMPONENTS[id];
  if (!Comp) return null;
  return <Comp {...unwrap(payload)} />;                        // generic (seed)
}

export const registeredCardIds = (): number[] =>
  Array.from(new Set([...Object.keys(FILL), ...Object.keys(COMPOSE), ...Object.keys(COMPONENTS)].map(Number))).sort((a, b) => a - b);
