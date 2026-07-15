/**
 * AiSummary.tsx — a self-contained COPY of CMD_V2's AiSummary primitive
 * (CMD_V2/src/components/charts/primitives/AiSummary.tsx), brought into this
 * repo so the Layer-3 page summary carries the exact Neuract DS look without a
 * cross-tree token import.
 *
 * Figma source (Neuract DS): node 2499:9047 — a glowing golden ✦ sparkle in a
 * 16px column, 4px gap, body text = IBM Plex Sans 13px teal700, 1.55 leading.
 * The two design tokens the primitive uses are inlined below verbatim from the
 * CMD_V2 token files (colors.ts gold600 / teal700, typography.ts insightText).
 *
 * Usage:
 *   <AiSummary text="Current peaked at 366 A at 18:00…" />
 *   <AiSummary text="…" withIcon={false} />   // bare text
 */
import type { CSSProperties } from "react";

// ── tokens (verbatim from CMD_V2 colors.ts / typography.ts) ──────────────────────────────────────────────
const GOLD_600 = "#b88528"; // golden — AI insight ✦ sparkle (Figma 2499:9047)
const TEAL_700 = "#134760"; // insight body text
const INSIGHT_TEXT: CSSProperties = {
  fontFamily: "'IBM Plex Sans', var(--font-sans), system-ui, sans-serif",
  fontSize: 13,
  fontWeight: 400,
  color: TEAL_700,
  lineHeight: 1.55,
  letterSpacing: 0,
};
/** Soft golden halo behind the sparkle (Figma 2499:9047). */
const ICON_GLOW = "0px 0px 6px rgba(184, 133, 40, 0.6), 0px 0px 14px rgba(184, 133, 40, 0.3)";

interface AiSummaryProps {
  text: string;
  /** Size/position classes — e.g. `mt-auto`, `w-full`. */
  className?: string;
  /** Compact density tightens the line-height for bounded cards. */
  density?: "regular" | "compact";
  /** The ✦ sparkle column (Figma 2499:9047). On by default. */
  withIcon?: boolean;
}

export function AiSummary({ text, className, density = "regular", withIcon = true }: AiSummaryProps) {
  const compact = density === "compact";
  const bodyStyle: CSSProperties = compact ? { ...INSIGHT_TEXT, fontSize: 12, lineHeight: 1.5 } : INSIGHT_TEXT;

  if (!withIcon) {
    return (
      <p className={`min-w-0 ${className ?? ""}`} style={bodyStyle}>
        {text}
      </p>
    );
  }

  return (
    <div className={`flex min-w-0 items-start gap-1 ${className ?? ""}`}>
      <span
        aria-hidden="true"
        className="w-4 shrink-0 text-center"
        style={{ color: GOLD_600, fontSize: 14, lineHeight: "20px", textShadow: ICON_GLOW }}
      >
        ✦
      </span>
      <p className="min-w-0 flex-1" style={bodyStyle}>
        {text}
      </p>
    </div>
  );
}
