import React from "react";
import type { Card, DateWindow } from "../types";
import { renderCmd } from "../cmd/registry";
import { fetchCardFrame } from "../api";

class Boundary extends React.Component<{ children: React.ReactNode }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: any) { return { err: String(e?.message ?? e) }; }
  render() {
    if (this.state.err) return <div className="placeholder"><div className="big">⚠</div><div>render error</div><div className="k">{this.state.err}</div></div>;
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

  const consumer = (card as any).data_instructions?.consumer;
  const onDateChange = React.useCallback((dw: DateWindow) => {
    if (!consumer) return;
    fetchCardFrame(consumer, dw).then((f) => { if (f) setFrame(f); }).catch(() => {});
  }, [consumer]);

  // SAFE-RENDER [FR-1]: the renderCmd() CALL itself can THROW (a fill mapper reading a malformed frame, an unwrap on a
  // bad payload) — and that throw happens DURING this component's render, OUTSIDE <Boundary> (which only catches throws
  // from the already-built `node`). Wrapping the call in try/catch stops a single bad card from white-screening the app.
  let node: React.ReactNode = null;
  let renderErr: string | null = null;
  try {
    node = renderCmd(card, frame, onDateChange, pageFrame ?? liveFrame);
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
    </div>
  );
  return (
    <div style={{ position: "relative", height: h ?? "100%", minHeight: 0, overflow: "auto" }}>
      <ValidationDot card={card} />
      {reason ? (
        <span title={reason}
          style={{ position: "absolute", top: 6, left: 6, zIndex: 5, fontSize: 10, opacity: 0.55, cursor: "help" }}>ⓘ</span>
      ) : null}
      <Boundary>{node}</Boundary>
    </div>
  );
}
