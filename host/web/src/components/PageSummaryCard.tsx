import { useEffect, useState } from "react";
import { fetchPageSummary } from "../api";
import { AiSummary } from "./AiSummary";

// PAGE SUMMARY — the Layer-3 AI narrator's output, rendered in CMD_V2's AiSummary primitive (✦ gold sparkle +
// teal insight text, Figma 2499:9047). Sits directly below the validation bar, above the grid. LAZY: fires
// AFTER the run (keyed by run_id) so the grid paints instantly and the story streams in a beat later; never
// blocks the page. Honest-degrade: an empty/failed summary renders nothing.
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
  if (!loading && !text) return null;                  // honest-degrade: no summary → nothing

  return (
    <div className="cc-summary" role="note" aria-label="AI summary">
      <AiSummary text={loading && !text ? "reading the page…" : text} className={loading && !text ? "cc-summary-loading" : ""} />
    </div>
  );
}
