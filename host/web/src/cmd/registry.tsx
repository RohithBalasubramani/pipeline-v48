// CARD_ID-KEYED REGISTRY — DIRECT COMPLETED-PAYLOAD RENDER (2026-07-02).
// The host now returns each card's COMPLETED payload (card.payload = the ems_exec-filled CMD V2 props for data cards, OR
// a run_special widget-envelope for the special cards) and `frames` is EMPTY. So the payload IS the props — we render the
// card's OWN CMD V2 component from it DIRECTLY. Tiers tried in order by render_card_id (the swap target if Layer 2 swapped,
// else the card itself), so a swapped-in card from another page renders by its OWN identity:
//   1. SPECIAL[id] / envelope-detect — cards whose completed payload is a {widgets:{ai_summary|sld}} / {object,viewer}
//                    ENVELOPE, not props (narrative_ai 8/28, asset_3d 60, topology_sld) → the CMD V2 primitive for it.
//   2. FILL[id]     — the card's OWN per-card fill module WINS over the generic spread (2026-07-06): it exists precisely
//                    because its component needs a guarded/finitized view-model and/or per-card date-control wiring;
//                    letting COMPONENTS shadow FILL bypassed every guard the fill was built to apply.
//   3. COMPONENTS[id] — DIRECT render of the card's REAL CMD V2 component, <Component {...unwrap(payload)}> straight
//                    from the completed payload (payload = props; frames are empty).
//   4. COMPOSE[id]  — bespoke glue for the few stacked cards (card 5 RTM heatmap) + RTM chrome atoms.
//   5. HonestBlank  — no renderable component → the honest machine-reason blank, never a crash.
//
// SPLIT (F11, 2026-07-12): one file per concern in cmd/registry/ — fill-loader (the glob, now "../fill/*.tsx"),
// unwrap, force-blank, gap-info (the stateful marker), render-cmd (the dispatcher), ids. THIS file is the pure
// re-export barrel so every import path (CmdCard, RtmComposite, scripts/tier_audit, ssr_gate/ssr_repro) stays
// byte-stable.
export { renderCmd } from "./registry/render-cmd";
export { unwrap } from "./registry/unwrap";
export { forceBlank } from "./registry/force-blank";
export { FILL, type RenderFn } from "./registry/fill-loader";
export { GapInfo, gapSentences, withGaps, type GapRecord } from "./registry/gap-info";
export { registeredCardIds } from "./registry/ids";
