import React from "react";

// The ONE honest-blank placeholder — the render-contract's most load-bearing UI (an honest data gap shows the card's
// own frame + the machine reason; NOT a fabricated value, NOT a white screen). Previously three near-identical
// copies (registry HonestBlank, CmdCard boundary fallback, CmdCard no-node branch). [contract: honest blank+reason]
export function HonestBlankTile({ glyph = "—", title, reason, note, style, children }: {
  glyph?: string;
  title?: string | null;
  reason?: string | null;
  /** B1: Layer 2's plain-words proxy/substitution data_note (placeholder path only). */
  note?: string | null;
  style?: React.CSSProperties;
  /** Extra chrome overlaid on the tile (e.g. the per-card ValidationDot). */
  children?: React.ReactNode;
}): React.ReactNode {
  return (
    <div className="placeholder" style={{ height: "100%", minHeight: 0, ...style }}>
      {children}
      <div className="big">{glyph}</div>
      <div>{title || "no live data"}</div>
      {reason ? <div className="k">{reason}</div> : null}
      {note ? <div className="k">{note}</div> : null}
    </div>
  );
}
