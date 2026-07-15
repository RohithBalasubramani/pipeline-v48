import { useEffect, useState } from "react";
import { fetchPageSummary } from "../api";

// PAGE SUMMARY — the Layer-3 AI narrator's output. Rendered as a compact card directly below the validation bar,
// above the grid. LAZY on purpose: it fires AFTER the run (keyed by run_id) so the grid paints instantly and the
// story streams in a beat later; it never blocks the page. Honest-degrade: an empty/failed summary renders nothing.
export function PageSummaryCard({ runId }: { runId: string | null | undefined }) {
  const [text, setText] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!runId) { setText(""); return; }
    let alive = true;
    setLoading(true);
    setText("");
    fetchPageSummary(runId)
      .then((d) => { if (alive) setText((d.summary || "").trim()); })
      .catch(() => { if (alive) setText(""); })       // decoration, never load-bearing — a failure just shows nothing
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [runId]);

  if (!runId) return null;
  if (!loading && !text) return null;                  // honest-degrade: no summary → no card

  return (
    <div className="cc-summary" role="note" aria-label="AI page summary">
      <span className="cc-summary-tag">AI SUMMARY</span>
      {loading && !text ? (
        <span className="cc-summary-loading">reading the page…</span>
      ) : (
        <p className="cc-summary-text">{text}</p>
      )}
    </div>
  );
}
