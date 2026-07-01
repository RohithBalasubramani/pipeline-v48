import { useState } from "react";
import { runPipeline } from "./api";
import type { PipelineResult } from "./types";
import { CommandHeader } from "./components/CommandHeader";
import { SuggestedCommands } from "./components/SuggestedCommands";
import { CardGrid } from "./components/CardGrid";
import { AssetResolution } from "./components/AssetResolution";
import type { Seed } from "./components/PromptBar";

// Command Center — the Neuract host shell. Header (brand + copilot bar + LIVE status) is always on; below it the
// workspace cycles through: suggested-commands empty state → "copilot running" → the resolved CardGrid. When 1b can't
// pin one asset the resolution popup overlays the shell (ambiguous / empty / terminal / resolved) before Layer 2 runs.
export function App() {
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");
  const [seed, setSeed] = useState<Seed>({ text: "", n: 0 });
  const [resolving, setResolving] = useState(false);   // asset-resolution popup flow is active

  const run = async (prompt: string, assetId?: number) => {
    setLoading(true);
    setError(null);
    setLastPrompt(prompt);
    try {
      const r = await runPipeline(prompt, assetId);
      setResult(r);
      // open/keep the resolution popup when 1b is ambiguous/empty, while a pinned pick re-runs (→ "resolved" view), OR
      // when the named asset is NO-DATA (the picker opens with it greyed + alternatives; "None of these" → no-data
      // terminal). Everything no-data is resolved AT THE PICKER — it never proceeds to Layer 2. [no_data → picker, hybrid]
      setResolving((r as any).asset_pending === true || (r as any).asset_no_data === true || assetId != null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResult(null);
      setResolving(false);
    } finally {
      setLoading(false);
    }
  };

  const pickSuggested = (q: string) => setSeed((s) => ({ text: q, n: s.n + 1 }));

  // NO-DATA: 1b resolved the named asset but its neuract table is empty → handled IN the picker now (opens greyed +
  // alternatives; "None of these" → no-data terminal), so it never falls through to the card grid or reaches Layer 2.
  const noData = !!result && (result as any).asset_no_data === true;
  const hasCards = !!result && !(result as any).asset_pending && !noData && !loading && !resolving;

  return (
    <div className="cc-shell">
      <CommandHeader onRun={(p) => run(p)} loading={loading} seed={seed} />

      {hasCards ? (
        <div className="cc-results">
          <ValidationBar validation={(result as any).validation} cards={result!.cards} />
          <div className="cc-grid-fill">
            <CardGrid
              cards={result!.cards}
              layout={(result as any).page?.layout}
              frames={(result as any).frames}
              liveFrame={(result as any).live_frame}
            />
          </div>
        </div>
      ) : (
        <main className="cc-work">
          <div className="cc-work-inner">
            {loading && !resolving ? <RunningCard query={lastPrompt} /> : <SuggestedCommands onPick={pickSuggested} />}
            {error && !loading && (
              <div className="cc-fatal">
                Pipeline request failed: {error}
                <div style={{ marginTop: 6, opacity: 0.85 }}>
                  Is the API up? <code>python3 host/server.py</code> (default :8770)
                </div>
              </div>
            )}
          </div>
        </main>
      )}

      {/* ASSET RESOLUTION — gated BEFORE Layer 2. Pick → re-run pinned → "resolved" → Open dashboard reveals the cards.
          None of these → terminal (pipeline ends). Dismiss → back to the empty state. */}
      {resolving && result && (
        <AssetResolution
          candidates={result.asset.candidates}
          noDataAsset={((result as any).asset_no_data || (result as any).validation_blocked) ? (result.asset?.asset ?? null) : null}
          blockKind={(result as any).validation_blocked ? "validation" : "no_data"}
          prompt={lastPrompt}
          loading={loading}
          onPick={(id) => run(lastPrompt, id)}
          onOpenDashboard={() => setResolving(false)}
          onDismiss={() => {
            setResolving(false);
            setResult(null);
            setSeed((s) => ({ text: lastPrompt, n: s.n + 1 }));   // refocus the prompt bar, pre-filled to refine
          }}
        />
      )}
    </div>
  );
}

// NO-DATA notice now lives INSIDE the picker (AssetResolution): a no_data result opens the picker with the named asset
// greyed + alternatives, and "None of these" → the picker's no-data terminal. (The standalone NoDataNotice was folded in.)

// VALIDATION BAR — surfaces the validate layer in the live view (was orphaned when the app moved to the clean CardGrid):
// page verdict + the data/payload summaries + a per-card fail/warn rollup. Thin strip above the grid; never blocks.
function ValidationBar({ validation, cards }: { validation: any; cards: any[] }) {
  if (!validation) return null;
  const v = (validation.verdict as string | null) ?? null;
  const ds = validation.data_summary as any;
  const ps = validation.payload_summary as any;
  const fails = cards.filter((c) => c?.validation?.verdict === "fail").length;
  const warns = cards.filter((c) => c?.validation?.verdict === "warn").length;
  const color = v === "fail" ? "#d4351c" : v === "warn" ? "#d9a300" : "#3a7d44";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "5px 14px", fontSize: 12,
                  fontFamily: "var(--font-mono, ui-monospace, monospace)", color: "#5b6168",
                  background: "#f3efe6", borderBottom: "1px solid #e6e0d4" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color, fontWeight: 600 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: color }} />
        validation · {v ?? "n/a"}
      </span>
      {ds && <span>data {ds.n_pass ?? 0}/{ds.n_columns ?? 0} cols{ds.n_fail ? ` · ${ds.n_fail} fail` : ""}{ds.n_warn ? ` · ${ds.n_warn} warn` : ""}</span>}
      {ps && <span>payload {ps.n_pass ?? 0}/{ps.n_cards ?? 0} cards{ps.n_fail ? ` · ${ps.n_fail} fail` : ""}</span>}
      {(fails || warns) ? <span style={{ marginLeft: "auto" }}>{fails} fail · {warns} warn (cards)</span> : null}
    </div>
  );
}

// "Copilot running" — the design's last-run confirmation, driven by the live pipeline call.
function RunningCard({ query }: { query: string }) {
  return (
    <div className="cc-lastrun">
      <span className="spark">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z" />
        </svg>
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="cc-lastrun-label">Working</div>
        <div className="cc-lastrun-q">{query}</div>
        <div className="cc-lastrun-meta" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="spinner" /> Building your real-time view…
        </div>
      </div>
    </div>
  );
}
