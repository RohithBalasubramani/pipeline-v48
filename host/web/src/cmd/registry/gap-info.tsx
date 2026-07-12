// registry/gap-info.tsx — the EXPLAINED-BLANKS (i) marker: gapSentences + GapInfo + withGaps
// (split F11, 2026-07-12 — a stateful React component no longer lives inside the dispatch module).
import React from "react";
import type { GapRecord } from "../../types";

export type { GapRecord } from "../../types";   // re-exported for existing importers

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
// (GapRecord re-exported in the header above — declared beside the response mirror in ../../types)

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
export function withGaps(node: React.ReactNode, gaps?: GapRecord[] | null, note?: string | null,
                  answerability?: string | null): React.ReactNode {
  if (!node || (!gapSentences(gaps).length && !(note ?? "").trim())) return node;
  return (<>{node}<GapInfo gaps={gaps} note={note} answerability={answerability} corner /></>);
}
