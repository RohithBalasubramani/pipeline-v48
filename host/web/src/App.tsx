import { useState } from "react";
import { runPipeline } from "./api";
import type { PipelineResult } from "./types";
import { CommandHeader } from "./components/CommandHeader";
import { SuggestedCommands } from "./components/SuggestedCommands";
import { CardGrid } from "./components/CardGrid";
import { KnowledgeAnswer, type KnowledgeTurn } from "./components/KnowledgeAnswer";
import { AssetResolution } from "./components/AssetResolution";
import { DataUnavailable } from "./components/DataUnavailable";
import type { Seed } from "./components/PromptBar";

// Command Center — the Neuract host shell. Header (brand + copilot bar + LIVE status) is always on; below it the
// workspace cycles through: suggested-commands empty state → "copilot running" → the resolved CardGrid. When 1b can't
// pin one asset the resolution popup overlays the shell (ambiguous / empty / terminal / resolved) before Layer 2 runs.
// REFRESH → MAIN SCREEN — the dashboard lives only in React state. We persist the last COMPLETED card result in
// sessionStorage, BUT a full page reload (hard refresh / F5 / dev HMR full-reload) intentionally returns to the empty
// main screen instead of re-showing the last dashboard: a user hits refresh to get a clean slate. We detect the reload
// via the Navigation Timing API and drop the saved dashboard on mount. Session-scoped on purpose — a new tab starts
// clean too. Restore-on-mount is thus a deliberate no-op for reloads; the save is kept harmlessly for any future
// non-reload rehydration path.
const _SAVED_KEY = "v48:last_dashboard";
function _isPageReload(): boolean {
  // A hard refresh / F5 reports navigation type "reload" (JS cannot distinguish a hard from a soft reload — and either
  // should land on the main screen). A fresh navigation / new tab reports "navigate". Fail-open to NOT-a-reload so a
  // normal first load still restores nothing unexpectedly (sessionStorage is empty on a fresh tab anyway).
  try {
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (nav && typeof nav.type === "string") return nav.type === "reload";
    return (performance as any).navigation?.type === 1;   // legacy fallback: PerformanceNavigation.TYPE_RELOAD === 1
  } catch { return false; }
}
function _loadSaved(): { prompt: string; result: PipelineResult } | null {
  try {
    if (_isPageReload()) { sessionStorage.removeItem(_SAVED_KEY); return null; }  // refresh → main screen, not the last dashboard
    const raw = sessionStorage.getItem(_SAVED_KEY);
    if (!raw) return null;
    const d = JSON.parse(raw);
    return d && d.result && Array.isArray(d.result.cards) && d.result.cards.length ? d : null;
  } catch { return null; }
}
function _save(prompt: string, result: PipelineResult) {
  try { sessionStorage.setItem(_SAVED_KEY, JSON.stringify({ prompt, result })); } catch { /* quota — skip, never break the run */ }
}

export function App() {
  const saved = _loadSaved();
  const [result, setResult] = useState<PipelineResult | null>(saved?.result ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPrompt, setLastPrompt] = useState(saved?.prompt ?? "");
  const [seed, setSeed] = useState<Seed>({ text: "", n: 0 });
  const [resolving, setResolving] = useState(false);   // asset-resolution popup flow is active
  // KNOWLEDGE conversation thread — the running Q&A turns (oldest-first). Carried back to the one AI layer as `history`
  // so a follow-up ("how is it measured") resolves in context; cleared the moment a prompt routes to the card pipeline.
  const [thread, setThread] = useState<KnowledgeTurn[]>([]);

  const run = async (prompt: string, assetId?: number | number[]) => {
    setLoading(true);
    setError(null);
    setLastPrompt(prompt);
    // A fresh prompt (no pinned asset) carries the knowledge thread as follow-up context; an asset re-pick does not.
    const history = assetId == null ? thread.map((t) => ({ prompt: t.prompt, answer: t.answer })) : [];
    const isMulti = Array.isArray(assetId);   // MULTI-ASSET compare: skip the "resolved" popup, reveal the grouped grid
    try {
      const r = await runPipeline(prompt, assetId, null, history);
      setResult(r);
      // persist a COMPLETED dashboard (cards present, nothing pending) so a page reload restores it instead of
      // resetting to the main screen; a pending/knowledge/empty result never overwrites the last good dashboard.
      if ((r as any).kind !== "knowledge" && !(r as any).asset_pending && Array.isArray(r.cards) && r.cards.length) {
        _save(prompt, r);
      }
      if ((r as any).kind === "knowledge") {
        // append this turn to the thread (a refused/off-scope turn is shown too, as OUT OF SCOPE)
        setThread((t) => [...t, { prompt, answer: (r as any).answer, refused: !!(r as any).refused }]);
      } else {
        setThread([]);   // routed to the card/asset pipeline → new topic, drop the conversation
      }
      // open/keep the resolution popup when 1b is ambiguous/empty, while a pinned pick re-runs (→ "resolved" view), OR
      // when the named asset is NO-DATA (the picker opens with it greyed + alternatives; "None of these" → no-data
      // terminal). Everything no-data is resolved AT THE PICKER — it never proceeds to Layer 2. [no_data → picker, hybrid]
      // A multi-asset compare pins every asset up-front → go straight to the grouped grid (never the single "resolved" card).
      setResolving(!isMulti && ((r as any).asset_pending === true || (r as any).asset_no_data === true || assetId != null));
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
  // KNOWLEDGE pipeline (separate, 2026-07-06): a conceptual electrical/mechanical answer or the domain refusal —
  // rendered as ONE text panel, never the card grid.
  const knowledge = !!result && (result as any).kind === "knowledge";
  const hasCards = !!result && !knowledge && !(result as any).asset_pending && !noData && !loading && !resolving;
  // HONEST OUTAGE: a data_unavailable terminal (e.g. the neuract tunnel dropped) OR a resolved run that produced ZERO
  // cards must show a clear notice — NOT a silent blank grid. Covers the single AND the multi-asset response.
  const outage = hasCards && ((result as any).data_unavailable === true || (result!.cards?.length ?? 0) === 0);

  return (
    <div className="cc-shell">
      <CommandHeader onRun={(p) => run(p)} loading={loading} seed={seed} />

      {knowledge && !loading ? (
        <main className="cc-work">
          <KnowledgeAnswer turns={thread} />
        </main>
      ) : outage ? (
        <main className="cc-work">
          <div className="cc-work-inner">
            <DataUnavailable prompt={lastPrompt} onRetry={(p) => run(p)} />
          </div>
        </main>
      ) : hasCards ? (
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
