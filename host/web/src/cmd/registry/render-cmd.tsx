// registry/render-cmd.tsx — renderCmd, the 5-tier dispatcher (split F11, 2026-07-12; tier doc in ../registry.tsx).
import React from "react";
import { COMPONENTS } from "../components";
import { COMPOSE } from "../compose";
import { guardPayload } from "../guards";
import { SPECIAL, ENVELOPE_RENDERERS, isNarrativeEnvelope, isTopologyEnvelope, isAsset3dEnvelope } from "../special";
import { dateControlProps } from "../date-adapter";
import { HonestBlankTile as HonestBlank } from "../../components/HonestBlankTile";
import type { Card, RenderVerdict } from "../../types";
import { FILL } from "./fill-loader";
import { PRIM } from "../prim";
import { unwrap } from "./unwrap";
import { forceBlank } from "./force-blank";
import { withGaps } from "./gap-info";

/** Render a pipeline card with its REAL CMD V2 component from the card's OWN completed payload (payload = props;
 *  the page-frame plumbing is retired — F14, 2026-07-12). null → caller shows the placeholder.
 *  The render-guarantee verdict (card.render) is OBEYED: a honest_blank verdict short-circuits to an honest reason card
 *  (never a seed), and suppress_default_leaves are force-blanked in the payload before it reaches the component. */
export function renderCmd(
  card: Card | null | undefined,
  onDateChange?: (dw: any) => void,
): React.ReactNode {
  if (!card) return null;
  const rv: RenderVerdict = card.render ?? {};
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
  // The fill fns keep their historical (payload, frame?, onDateChange?, pageFrame?) arity — the frame slots are
  // permanently undefined now (retired wire fields); fills fill from the payload alone.
  // 2a. PRIM — the PRIMITIVES-ONLY registry [no-page-cards port, 2026-07-12]: payload → CMD_V2 primitive adapters
  //     (docs/primitives_inventory/PORT_CONTRACT.md); header/legends/colors/values all ride the payload. Wins over the
  //     legacy page-card tiers; those survive only for ids not yet ported and are deleted when the port completes.
  if (PRIM[id]) return withGaps(PRIM[id](pg, onDateChange), rv.gaps, dnote, l2ans);

  if (FILL[id]) return withGaps(FILL[id](pg, undefined, onDateChange, undefined), rv.gaps, dnote, l2ans);

  // 3. COMPONENTS — DIRECT render of the card's REAL CMD V2 component from the completed payload (cards whose props are
  //    spread-safe without a per-card view-model). PER-CARD DATE NAVIGATION [time-series]: a date-navigable (is_history)
  //    card gets the CMD_V2 date-control callback (onRangeChange) wired to the host re-fetch, so a range pick re-fills
  //    THIS card for the new window (/api/frame). No CMD_V2 change — the panel-overview cards already accept the prop;
  //    a component that ignores it is unaffected. FILL-tier cards wire their own onDateChange, so this is COMPONENTS-only.
  const Comp = COMPONENTS[id];
  if (Comp) {
    const dateProps = card.is_history ? dateControlProps(onDateChange) : {};
    return withGaps(<Comp {...unwrap(pg)} {...dateProps} />, rv.gaps, dnote, l2ans);
  }

  // 4. COMPOSE — bespoke glue for stacked cards (card 5) + the RTM chrome atoms (6/160, which carry no card_payloads
  //    skeleton) — the empty-object payload draws their own default chrome / empty state on no_data.
  const glue = COMPOSE[id];
  if (glue) return withGaps(glue(pg), rv.gaps, dnote, l2ans);

  // 5. NO renderable component (e.g. an overview-shell tile with no card_payloads) → the honest machine-reason blank,
  //    never a crash. This is the ONLY place the generic placeholder shows now.
  if (rv.verdict === "honest_blank" || !payload) {
    return <HonestBlank title={card.title} reason={rv.reason || rv.coverage_note} />;
  }
  return null;
}
