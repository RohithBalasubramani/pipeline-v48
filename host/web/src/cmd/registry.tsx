import React from "react";
import { COMPONENTS } from "./components";
import { COMPOSE } from "./compose";
import { guardPayload, aiHeadlineOf } from "./guards";
import { SPECIAL, ENVELOPE_RENDERERS, isNarrativeEnvelope, isTopologyEnvelope, isAsset3dEnvelope } from "./special";

// CARD_ID-KEYED REGISTRY — DIRECT COMPLETED-PAYLOAD RENDER (2026-07-02).
// The host now returns each card's COMPLETED payload (card.payload = the ems_exec-filled CMD V2 props for data cards, OR
// a run_special widget-envelope for the special cards) and `frames` is EMPTY. So the payload IS the props — we render the
// card's OWN CMD V2 component from it DIRECTLY. Tiers tried in order by render_card_id (the swap target if Layer 2 swapped,
// else the card itself), so a swapped-in card from another page renders by its OWN identity:
//   1. SPECIAL[id] / envelope-detect — cards whose completed payload is a {widgets:{ai_summary|sld}} / {object,viewer}
//                    ENVELOPE, not props (narrative_ai 8/28, asset_3d 60, topology_sld) → the CMD V2 primitive for it.
//   2. COMPONENTS[id] — the card's REAL CMD V2 component, rendered <Component {...unwrap(payload)}> straight from the
//                    completed payload. THE PRIMARY PATH (payload = props; frames are empty).
//   3. COMPOSE[id]  — bespoke glue for the few stacked cards (card 5 RTM heatmap).
//   4. FILL[id]     — LAST RESORT ONLY. The old per-page mapper-fill read the (now-EMPTY) live frame; a handful of cards
//                    whose payload can't populate their component alone (they need a module-default view-model, or carry
//                    NO Storybook payload: 61/62/63/64/65/71/73) fall here and honest-degrade to CMD V2's OWN typed-empty
//                    view-model (the fill view-models return the empty baseline for an absent frame) — never a crash.
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

// "OPEN THE BOX" — the completed payload wraps the real props one level down under a SINGLE key (+ a throwaway
// `variant`), e.g. {variant, batteryHealth} / {variant, rail} / {variant, thermalLife}. The card's CMD V2 component
// reads that inner object under a prop name that VARIES per card — the Storybook `render` renames it: `railVM` reads it
// as-is, but most read it as `data` (BatteryHealthCard, HealthSummaryPanel, …), `vm` (ThermalLifeCard, tap cards, …) or
// `view` (LiveOpsCard, UpsCapacityCard, …). Since a card reads exactly ONE of these, we make the inner object available
// under ALL of them (data/vm/view) PLUS its own key PLUS spread its fields — so every prop shape is satisfied and the
// extras React harmlessly ignores. Multi-key payloads ({data,freshness} / {snapshot,display}) fall to the spread branch,
// which is already the correct multi-prop shape.
const SINGLE_OBJECT_PROP_ALIASES = ["data", "vm", "view"] as const;
// (exported for scripts/tier_audit.tsx — the FILL-vs-COMPONENTS tier comparison harness renders the direct-spread
// path with the exact same unwrap/forceBlank preprocessing renderCmd applies.)
// Keys that are NOT component props: the Storybook `variant` probe, and the narrative_ai envelope keys the host grafts
// onto a props-shaped payload (`widgets.ai_summary` + a mirrored top-level `ai_summary`). Ignoring them when we find the
// single spreadable prop keeps a props-card (19/25 AiSummary) single-key even after its ai_summary widget is attached.
// `loading` is also non-prop for key-shape detection (guards g16 sets it on the ROOT beside the vm key — it must not
// break the single-spreadable-prop unwrap) but IS forwarded as a real prop below (the CMD_V2 socket-loading seam).
const NON_PROP_KEYS = new Set(["variant", "widgets", "ai_summary", "loading"]);
export function unwrap(payload: any): any {
  if (!payload || typeof payload !== "object") return payload;
  // BACKEND-PARAGRAPH PROP [family H, cards 19/25 class]: a card that carries its REAL generated ai_summary text also
  // exposes it under the CMD_V2-designed `backendAiSummary` prop name (PqAiSummaryCard takes it as a prop and then
  // SKIPS its local compose — which is unguarded against honest-blank stats). Real text only; harmless extra prop for
  // every component that doesn't declare it.
  const aiText = aiHeadlineOf(payload);
  const withAi = (out: any) => {
    if (aiText && out && typeof out === "object" && out.backendAiSummary == null) out.backendAiSummary = aiText;
    // g16 seam: the guards mark a fully-unmeasured zero-row plot with root `loading` — forward it as the component's
    // own socket-loading prop (skeleton chrome) without disturbing key-shape detection above. Never clobbers.
    if (payload.loading === true && out && typeof out === "object" && out.loading == null) out.loading = true;
    return out;
  };
  const keys = Object.keys(payload).filter((k) => !NON_PROP_KEYS.has(k));
  if (keys.length === 1) {
    const key = keys[0];
    const inner = payload[key];
    if (inner && typeof inner === "object" && !Array.isArray(inner)) {
      const out: any = { ...inner, [key]: inner };
      // Alias the inner object to the common single-object prop names — but NEVER clobber a real field the inner
      // already carries (a spread-consumer might read it) or the payload's own key.
      for (const alias of SINGLE_OBJECT_PROP_ALIASES) {
        if (alias !== key && !(alias in out)) out[alias] = inner;
      }
      return withAi(out);
    }
  }
  const { variant, ...rest } = payload;
  const out: any = rest;
  // INNER-ALIAS HOIST [family H, card 12 class]: a MULTI-key payload ({kpi, rail}) spreads as-is, but the component may
  // read a single-object prop (`vm`) that lives ONE level down inside one of those keys (rail.vm — the Storybook story
  // rendered the subcard from it). Surface each top-level dict's data/vm/view member under that name when the spread
  // itself doesn't carry it — never clobbering an existing prop. Generic (key-shape driven, no card ids).
  for (const v of Object.values(out)) {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      for (const alias of SINGLE_OBJECT_PROP_ALIASES) {
        if (!(alias in out) && alias in (v as any)) out[alias] = (v as any)[alias];
      }
    }
  }
  return withAi(out);
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
export function forceBlank(payload: any, paths?: string[]): any {
  if (!paths || !paths.length || !payload || typeof payload !== "object") return payload;
  let clone: any;
  try { clone = structuredClone(payload); } catch { clone = JSON.parse(JSON.stringify(payload)); }
  for (const p of paths) {
    const s = segs(p);
    let cur = clone;
    let ok = true;
    for (let i = 0; i < s.length - 1; i++) { if (cur == null) { ok = false; break; } cur = cur[s[i]]; }
    if (ok && cur != null && typeof cur === "object") {
      const k = s[s.length - 1];
      const existing = cur[k];
      // TYPE-PRESERVING blank: array stays [] (mapper .map()/.filter() render empty, never crash on null), object stays
      // {}, scalar → null (→ "—"). Fixes "Cannot read properties of null (reading 'map')". [NO-SEED-LEAK + no-crash]
      cur[k] = Array.isArray(existing) ? [] : (existing != null && typeof existing === "object" ? {} : null);
    }
  }
  return clone;
}

// HONEST-DASH lives SERVER-SIDE (host/display_dash.py, applied at the serve boundary): a unit-adjacent scalar null is
// dashed to '—' there, TYPE-PROVEN against the card's harvested default payload — the FE cannot tell a null display
// scalar from a legitimately-null OBJECT (e.g. supply.consumedHint), so no FE-side transform exists by design.

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

// ── EXPLAINED BLANKS [Issue C / Family-2] + DATA NOTE [B1 residual 'fe'] ─────────────────────────────────────────
// The executor classifies WHY each blank leaf is blank and the host rides the structured records on
// card.render.gaps = [{slot, cause, metric, fn?, reason}]. A PARTIAL card renders its real component with '—' tiles;
// this GENERIC affordance (no per-card logic) surfaces those reason sentences: a small (i) marker — the same
// unobtrusive style as the existing reason-ⓘ — whose tooltip AND click-expandable panel list the DEDUPED sentences,
// folding beyond GAP_FOLD behind '+N more'. It renders from render.gaps ONLY; honest_blank cards keep the existing
// HonestBlank reason display (the marker is additive telemetry, never a render gate).
// B1: the SAME marker also carries Layer 2's card-level `data_note` — the plain-words proxy/substitution disclosure
// ("kWh shown as a proxy for run-hours…") the host now serves per card — plus `l2_answerability`, L2's own claim
// (muted telemetry; render.answerability stays the derived truth). A card with a note but NO gap records (a fully-
// rendered proxy bind) still shows the marker: the disclosure matters MOST when every tile shows a number.
export type GapRecord = { slot?: string | null; cause?: string | null; metric?: string | null; fn?: string | null; reason?: string | null };

// Deduped WHOLE reason sentences carried by the gap records (order-preserving, blanks dropped).
export function gapSentences(gaps?: GapRecord[] | null): string[] {
  return Array.from(new Set((gaps ?? []).map((g) => (g?.reason ?? "").trim()).filter(Boolean)));
}

const GAP_FOLD = 5;                                        // sentences shown before the '+N more' disclosure

export function GapInfo({ gaps, note, answerability, corner }: {
  gaps?: GapRecord[] | null; note?: string | null; answerability?: string | null; corner?: boolean;
}): React.ReactNode {
  const [open, setOpen] = React.useState(false);
  const [showAll, setShowAll] = React.useState(false);
  const notes = gapSentences(gaps);
  const dnote = (note ?? "").trim();
  if (!notes.length && !dnote) return null;
  const shown = showAll ? notes : notes.slice(0, GAP_FOLD);
  const extra = notes.length - shown.length;
  const noteHead = `data note${answerability ? ` · AI answerability: ${answerability}` : ""}`;
  const tip = [
    dnote ? `${noteHead}: ${dnote}` : "",
    notes.length ? `why some values are blank:\n• ${notes.join("\n• ")}` : "",
  ].filter(Boolean).join("\n");
  const aria = [
    dnote ? "data note" : "",
    notes.length ? `${notes.length} blank-value reason${notes.length > 1 ? "s" : ""}` : "",
  ].filter(Boolean).join(" + ");
  return (
    <span className={`gapinfo${corner ? " corner" : ""}`}>
      <button type="button" className="gapinfo-i" title={tip}
        aria-label={aria}
        onClick={() => setOpen((o) => !o)}>ⓘ</button>
      {open && (
        <div className="gapinfo-pop" role="note">
          {dnote ? (
            <>
              <div className="gapinfo-head">{noteHead}</div>
              <div className="gapinfo-note">{dnote}</div>
            </>
          ) : null}
          {notes.length > 0 && (
            <>
              <div className="gapinfo-head">why some values are blank</div>
              <ul>{shown.map((s) => <li key={s}>{s}</li>)}</ul>
              {extra > 0 && (
                <button type="button" className="gapinfo-more" onClick={() => setShowAll(true)}>+{extra} more</button>
              )}
            </>
          )}
        </div>
      )}
    </span>
  );
}

// Attach the gap/data-note marker to a rendered card node WITHOUT touching its layout: a fragment sibling, absolutely
// anchored to the card's nearest positioned ancestor (the CmdCard wrapper). No-op when the records carry no reason
// sentence AND the card carries no data_note.
function withGaps(node: React.ReactNode, gaps?: GapRecord[] | null, note?: string | null,
                  answerability?: string | null): React.ReactNode {
  if (!node || (!gapSentences(gaps).length && !(note ?? "").trim())) return node;
  return (<>{node}<GapInfo gaps={gaps} note={note} answerability={answerability} corner /></>);
}

/** Render a pipeline card with its REAL CMD V2 component. `frame` = the live ems_backend frame for this card's endpoint
 *  (frames[card.endpoint]); a fill module maps it via the card's own CMD V2 mapper. null → caller shows the placeholder.
 *  The render-guarantee verdict (card.render) is OBEYED: a honest_blank verdict short-circuits to an honest reason card
 *  (never a seed), and suppress_default_leaves are force-blanked in the payload before it reaches the component. */
export function renderCmd(
  card: { card_id: number; render_card_id?: number; payload: any; title?: string; render?: any;
          data_note?: string | null; l2_answerability?: string | null } | null | undefined,
  frame?: any,
  onDateChange?: (dw: any) => void,
  pageFrame?: any,
): React.ReactNode {
  if (!card) return null;
  const rv = card.render || {};
  // B1 [residual 'fe']: Layer 2's card-level proxy/substitution disclosure + its own answerability claim — served
  // additively by the host and shown beside the gap sentences in the SAME (i) marker (withGaps on every tier below).
  const dnote = card.data_note ?? null;
  const l2ans = card.l2_answerability ?? null;
  // The completed payload is already honest-blanked SERVER-SIDE (real where neuract had it, null/'—' otherwise); we also
  // re-blank any suppress_default_leaves here (NO-SEED-LEAK). We DON'T short-circuit on the honest_blank verdict anymore:
  // frames are empty now, so we render the card's OWN CMD V2 component from the honest-blank payload — it draws its OWN
  // empty state (blank tiles / '—' / flat empty series), the real dashboard chrome, not a generic placeholder. The
  // machine-reason HonestBlank remains the FINAL fallback (below) for a card that has NO renderable component at all.
  const payload = forceBlank(card.payload, rv.suppress_default_leaves);  // NO-SEED-LEAK: blank unprovenanced leaves
  const id = card.render_card_id ?? card.card_id;
  // CHROME-CARD honest-blank [per-leaf-degradation]: a card with a registered renderer but NO payload (L2 skipped on
  // no_data / a pure-chrome card with no card_payloads skeleton — 6/160) should STILL render its real component from
  // its own static defaults / empty state, NOT the generic placeholder. Pass an EMPTY OBJECT to the renderer tiers so
  // a chrome/compose component draws its default chrome (a null would collapse it to the placeholder). The component's
  // own empty-state handling then draws honest-blank tiles — never fabricated data (no seed to leak from {}).
  const p0 = payload == null ? {} : payload;

  // 1. SPECIAL — the card's completed payload is a widget-ENVELOPE (not props). Pre-listed envelope-only ids first,
  //    then a defensive detect so a swapped-in card whose payload turned out to be an envelope still renders correctly.
  //    Every tier below is wrapped by withGaps: a card whose render.gaps carries per-leaf honest-gap reasons shows the
  //    generic (i) EXPLAINED-BLANKS marker over its real component. [Issue C — render.gaps only, no per-card logic]
  const special = SPECIAL[id];
  if (special) return withGaps(special(p0), rv.gaps, dnote, l2ans);
  if (isTopologyEnvelope(payload)) return withGaps(ENVELOPE_RENDERERS.topology_sld(payload), rv.gaps, dnote, l2ans);
  if (isNarrativeEnvelope(payload)) return withGaps(ENVELOPE_RENDERERS.narrative_ai(payload), rv.gaps, dnote, l2ans);
  if (!COMPONENTS[id] && isAsset3dEnvelope(payload)) return withGaps(ENVELOPE_RENDERERS.asset_3d(payload), rv.gaps, dnote, l2ans);

  // COMPONENT-SAFETY GUARDS [family H]: the CMD_V2 components are read-only and several leaf helpers are unguarded
  // (fmt(null), styles[''], value.toFixed) — deep-guard the payload (clone; per-leaf honest '—'/omission/neutral
  // chrome; zero fabrication) for the component/compose/fill tiers. Envelope payloads above are NEVER guarded (the
  // SLD/3D/narrative renderers own their null handling and '—' would corrupt their geometry). [guards.ts]
  const pg = guardPayload(p0);

  // 2. FILL — the card's OWN per-card fill module WINS over the generic spread: it exists precisely because its
  //    component needs a guarded/finitized view-model (unguarded fmt(null) crash class — card 41 fmtInt(efficiencyPct),
  //    2026-07-06) and/or the date-control wiring only the fill provides. 36 card_ids are registered in BOTH tiers;
  //    letting COMPONENTS shadow FILL bypassed every guard the fill was built to apply.
  if (FILL[id]) return withGaps(FILL[id](pg, frame, onDateChange, pageFrame), rv.gaps, dnote, l2ans);

  // 3. COMPONENTS — DIRECT render of the card's REAL CMD V2 component from the completed payload (cards whose props are
  //    spread-safe without a per-card view-model).
  const Comp = COMPONENTS[id];
  if (Comp) return withGaps(<Comp {...unwrap(pg)} />, rv.gaps, dnote, l2ans);

  // 4. COMPOSE — bespoke glue for stacked cards (card 5) + the RTM chrome atoms (6/160, which carry no card_payloads
  //    skeleton) — the empty-object payload draws their own default chrome / empty state on no_data.
  const glue = COMPOSE[id];
  if (glue) return withGaps(glue(pg, frame), rv.gaps, dnote, l2ans);

  // 5. NO renderable component (e.g. an overview-shell tile with no card_payloads) → the honest machine-reason blank,
  //    never a crash. This is the ONLY place the generic placeholder shows now.
  if (rv.verdict === "honest_blank" || !payload) {
    return <HonestBlank title={card.title} reason={rv.reason || rv.coverage_note} />;
  }
  return null;
}

export const registeredCardIds = (): number[] =>
  Array.from(new Set(
    [...Object.keys(SPECIAL), ...Object.keys(COMPONENTS), ...Object.keys(COMPOSE), ...Object.keys(FILL)].map(Number),
  )).sort((a, b) => a - b);
