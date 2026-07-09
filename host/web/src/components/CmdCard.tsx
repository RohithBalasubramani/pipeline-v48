import React from "react";
import type { Card, DateWindow } from "../types";
import { renderCmd } from "../cmd/registry";
import { fetchCardFrame } from "../api";
import { useDateSync } from "./DateSync";

// HONEST-BLANK on a deep component throw [FR-1 / frontend-contract crash family]: a CMD_V2 component can throw DURING
// React's render of the already-built node — e.g. an unguarded `data.activePowerAvgKw.toFixed()` when an honest-blank
// leaf arrived as '—'/null (card 40), or an object-array prop consumed as raw numbers (card 42). That throw is caught
// here. Rather than a generic "render error" box (which reads as a bug), we degrade to the card's OWN honest-blank tile
// (its title + the machine reason) so a single unrenderable leaf never masks the card as broken — the same per-leaf
// degradation contract the payload path already honors. GENERIC: no card id, driven by the passed title/reason.
class Boundary extends React.Component<{ children: React.ReactNode; title?: string; reason?: string | null },
                                       { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: any) { return { err: String(e?.message ?? e) }; }
  render() {
    if (this.state.err) return (
      <div className="placeholder" style={{ height: "100%", minHeight: 0 }}>
        <div className="big">—</div>
        <div>{this.props.title || "no live data"}</div>
        <div className="k">{this.props.reason || this.state.err}</div>
      </div>
    );
    return this.props.children;
  }
}

// Per-card VALIDATION indicator — surfaces the validate layer's per-card verdict (validate_payloads) in the live view.
// Subtle by design: pass shows nothing (clean), warn=amber, fail=red, with the reasons on hover. [validation in FE]
const VCOLOR: Record<string, string> = { warn: "#d9a300", fail: "#d4351c" };
function ValidationDot({ card }: { card: Card }) {
  const v = card.validation?.verdict;
  if (v !== "warn" && v !== "fail") return null;                  // pass / n-a → no clutter
  const reasons = card.validation?.reasons;
  const title = `validation: ${v}` + (reasons?.length ? `\n• ${reasons.join("\n• ")}` : "");
  return (
    <span title={title}
      style={{ position: "absolute", top: 6, right: 6, zIndex: 5, width: 9, height: 9, borderRadius: "50%",
               background: VCOLOR[v], boxShadow: "0 0 0 2px #faf8f3", cursor: "help" }} />
  );
}

// Render the card with its REAL CMD_V2 component (keyed by card_id). Each card owns a LOCAL frame: it starts from the
// page frame (frames[endpoint]) and is REPLACED when THIS card's own date control changes (PER-CARD date navigation —
// the card re-fetches only its own ems_backend frame for the new window, via /api/frame). onDateChange is handed to the
// card's fill renderer so the card's OWN CMD V2 date control (today/last-week/…) drives the re-fetch.
export function CmdCard({ card, h, liveFrame, pageFrame }: { card: Card; h?: number; liveFrame?: any; pageFrame?: any }) {
  const [frame, setFrame] = React.useState<any>(liveFrame);
  React.useEffect(() => { setFrame(liveFrame); }, [liveFrame]);   // new page run/date → reseed from the page frame

  // PER-CARD DATE NAVIGATION: the renderer fills from `card.payload` (the `frame` arg is inert now that frames are
  // retired), so an interactive date pick must SWAP the payload, not the frame. onDateChange re-fetches this card's
  // completed payload for the new window (/api/frame) and stores it as an override; a new page run/card drops it.
  // PAGE-LEVEL SYNC [DateSync]: a date pick PUBLISHES to the shared page window, and EVERY date-navigable card
  // re-fetches when that shared window changes — one control moves the whole page, like the CMD_V2 app's page filter.
  const { window: sharedWindow, setWindow: setSharedWindow } = useDateSync();
  const [payloadOverride, setPayloadOverride] = React.useState<any>(null);
  React.useEffect(() => { setPayloadOverride(null); }, [card]);   // new card/run → back to the page payload
  const onDateChange = React.useCallback((dw: DateWindow) => {
    setSharedWindow(dw);                                          // propagate to every card on the page
  }, [setSharedWindow]);
  React.useEffect(() => {                                         // any card's pick (incl. this one) → re-fetch mine
    if (!sharedWindow || !(card as any).is_history) return;
    let live = true;
    fetchCardFrame(card, sharedWindow).then((p) => { if (live && p) setPayloadOverride(p); }).catch(() => {});
    return () => { live = false; };
  }, [sharedWindow, card]);

  // SAFE-RENDER [FR-1]: the renderCmd() CALL itself can THROW (a fill mapper reading a malformed frame, an unwrap on a
  // bad payload) — and that throw happens DURING this component's render, OUTSIDE <Boundary> (which only catches throws
  // from the already-built `node`). Wrapping the call in try/catch stops a single bad card from white-screening the app.
  let node: React.ReactNode = null;
  let renderErr: string | null = null;
  try {
    const rc = payloadOverride ? { ...card, payload: payloadOverride } : card;
    node = renderCmd(rc, frame, onDateChange, pageFrame ?? liveFrame);
  } catch (e: any) {
    renderErr = String(e?.message ?? e);
  }

  // The render-guarantee reason channel: an honest blank/partial verdict, an empty/mismatched frame `why`, or a caught
  // render error — shown to the user instead of a bare box. [ER-6 / FR-1]
  const rv = (card as any).render || {};
  const fs = (card as any).frame_status || {};
  const reason = renderErr || rv.reason || rv.coverage_note || (fs.ok === false ? fs.why : null);

  if (!node) return (
    <div className="placeholder" style={{ position: "relative", height: h ?? "100%", minHeight: 0 }}>
      <ValidationDot card={card} />
      <div className="big">{renderErr ? "⚠" : rv.verdict === "honest_blank" ? "—" : "▦"}</div>
      <div>{card.title}</div>
      <div className="k">
        {renderErr ? `render error: ${renderErr}`
          : reason ? reason
          : `card #${card.card_id} — not wired yet`}
      </div>
      {/* B1: a card with NO renderable component never mounts the GapInfo marker — surface Layer 2's proxy/
          substitution data_note here so the disclosure is never lost on the placeholder path. */}
      {card.data_note ? <div className="k">{card.data_note}</div> : null}
    </div>
  );
  return (
    <div style={{ position: "relative", height: h ?? "100%", minHeight: 0, overflow: "auto" }}>
      <ValidationDot card={card} />
      {reason ? (
        <span title={reason}
          style={{ position: "absolute", top: 6, left: 6, zIndex: 5, fontSize: 10, opacity: 0.55, cursor: "help" }}>ⓘ</span>
      ) : null}
      <Boundary title={card.title} reason={rv.reason || rv.coverage_note}>{node}</Boundary>
    </div>
  );
}
