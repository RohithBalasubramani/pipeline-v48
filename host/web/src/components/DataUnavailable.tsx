import { useSiteStatus } from "../hooks/useSiteStatus";

// DB-DOWN / LIVE-DATA-OFFLINE panel — the honest terminal the user sees when the pipeline answered but there is no
// live data to render (the :5433 neuract link is down → response.data_unavailable, or a resolved run produced 0 cards).
// Not a dead-end: it POLLS /api/site every 12s and flips to a "CONNECTION RESTORED" state with a one-click reload of
// the same prompt the moment the link returns. Styled in the Command Center language (mono title, hairline card,
// status dot) — never a blank grid, never a raw red error. [honest outage UX]
export function DataUnavailable({ prompt, onRetry }: {
  prompt?: string;
  onRetry?: (prompt: string) => void;
}) {
  const { live, checkedAt } = useSiteStatus(12000);

  const canRetry = !!(prompt && onRetry);
  const dot = live ? "var(--sage-400, #7a9e6e)" : "#d9a300";

  return (
    <div style={{
      maxWidth: 640, margin: "48px auto 0", background: "#fff", border: "1px solid #e6e0d4",
      borderLeft: `3px solid ${dot}`, borderRadius: 10, padding: "22px 26px",
      boxShadow: "0 1px 2px rgba(31,61,58,0.04)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{
          width: 10, height: 10, borderRadius: "50%", background: dot, flex: "none",
          animation: live ? "none" : "ccPulse 1.6s ease-in-out infinite",
        }} />
        <div style={{ fontFamily: "var(--font-mono, ui-monospace, monospace)", fontWeight: 700, fontSize: 15,
                      letterSpacing: 0.6, color: "var(--teal-900, #1f3d3a)" }}>
          {live ? "CONNECTION RESTORED" : "LIVE DATA OFFLINE"}
        </div>
      </div>

      <div style={{ marginTop: 12, fontFamily: "var(--font-sans)", fontSize: 13.5, lineHeight: 1.55,
                    color: "var(--slate-500, #5b6168)" }}>
        {live
          ? "The live-data link is back. Reload to build this view with current meter readings."
          : "The live-data connection is unreachable, so no meter readings can be fetched right now. Nothing is shown rather than showing stale or made-up numbers. This panel re-checks the link every few seconds."}
      </div>

      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
        {canRetry && (
          <button
            className="cc-ar-btn"
            style={{ flex: "none", whiteSpace: "nowrap", opacity: live ? 1 : 0.55 }}
            disabled={!live}
            title={live ? "Re-run the same command with live data" : "Waiting for the live-data link…"}
            onClick={() => onRetry!(prompt!)}
          >
            {live ? "Reload dashboard" : "Waiting for connection…"}
          </button>
        )}
        <span style={{ fontFamily: "var(--font-sans)", fontSize: 11.5, color: "#a8a294" }}>
          {checkedAt ? `last checked ${checkedAt}` : "checking…"}
        </span>
      </div>
    </div>
  );
}
