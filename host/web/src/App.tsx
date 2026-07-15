import { useEffect, useState } from "react";
import { runPipeline } from "./api";
import { Spark } from "./components/icons";
import type { PipelineResult } from "./types";
import { CommandHeader } from "./components/CommandHeader";
import { SuggestedCommands } from "./components/SuggestedCommands";
import { CardGrid } from "./components/CardGrid";
import { PageSummaryCard } from "./components/PageSummaryCard";
import { DateSyncProvider } from "./components/DateSync";
import { KnowledgeAnswer, type KnowledgeTurn } from "./components/KnowledgeAnswer";
import { AssetResolution } from "./components/AssetResolution";
import { DataUnavailable } from "./components/DataUnavailable";
import { InspectorView } from "./components/InspectorView";
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
  // AI DECISION INSPECTOR — hash-synced view switch (no router lib, deliberately): #inspector is linkable and
  // back-button-able; everything else stays the state-driven command view.
  const [view, setView] = useState<"command" | "inspector">(() => (location.hash === "#inspector" ? "inspector" : "command"));
  useEffect(() => {
    const onHash = () => setView(location.hash === "#inspector" ? "inspector" : "command");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const openView = (v: "command" | "inspector") => {
    setView(v);
    const want = v === "inspector" ? "#inspector" : "";
    if (location.hash !== want) history.replaceState(null, "", location.pathname + location.search + want);
  };

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
      if (r.kind !== "knowledge" && !r.asset_pending && Array.isArray(r.cards) && r.cards.length) {
        _save(prompt, r);
      }
      if (r.kind === "knowledge") {
        // append this turn to the thread (a refused/off-scope turn is shown too, as OUT OF SCOPE)
        setThread((t) => [...t, { prompt, answer: r.answer ?? "", refused: !!r.refused }]);
      } else {
        setThread([]);   // routed to the card/asset pipeline → new topic, drop the conversation
      }
      // open/keep the resolution popup when 1b is ambiguous/empty, while a pinned pick re-runs (→ "resolved" view), OR
      // when the named asset is NO-DATA (the picker opens with it greyed + alternatives; "None of these" → no-data
      // terminal). Everything no-data is resolved AT THE PICKER — it never proceeds to Layer 2. [no_data → picker, hybrid]
      // A multi-asset compare pins every asset up-front → go straight to the grouped grid (never the single "resolved" card).
      setResolving(!isMulti && (r.asset_pending === true || r.asset_no_data === true || assetId != null));
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
  const noData = !!result && result.asset_no_data === true;
  // KNOWLEDGE pipeline (separate, 2026-07-06): a conceptual electrical/mechanical answer or the domain refusal —
  // rendered as ONE text panel, never the card grid.
  const knowledge = !!result && result.kind === "knowledge";
  const hasCards = !!result && !knowledge && !result.asset_pending && !noData && !loading && !resolving;
  // HONEST OUTAGE: a data_unavailable terminal (e.g. the neuract tunnel dropped) OR a resolved run that produced ZERO
  // cards must show a clear notice — NOT a silent blank grid. Covers the single AND the multi-asset response.
  const outage = hasCards && (result!.data_unavailable === true || (result!.cards?.length ?? 0) === 0);

  return (
    <div className="cc-shell">
      <CommandHeader onRun={(p) => { openView("command"); run(p); }} loading={loading} seed={seed}
                     onOpenInspector={() => openView("inspector")} />

      {view === "inspector" ? (
        <InspectorView initialTraceId={result?.trace_id ?? null} onBack={() => openView("command")} />
      ) : knowledge && !loading ? (
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
          <ValidationBar validation={result!.validation} cards={result!.cards} />
          <div className="cc-grid-fill">
            {/* DateSync keyed by run: one card's date pick re-fetches EVERY is_history card; a new prompt resets it */}
            <DateSyncProvider key={result!.run_id || lastPrompt}>
              <CardGrid cards={result!.cards} layout={result!.page?.layout} />
            </DateSyncProvider>
          </div>
          {/* FOOTER — the Layer-3 AI summary (left) shares the bottom row with the powered-by mark (right). */}
          <div className="cc-footer">
            <PageSummaryCard runId={result!.run_id} />
            <PoweredByNeuract inline />
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

      {/* fixed bottom-right badge for the non-results views (empty / knowledge / outage); in the results view the
          powered-by mark rides the footer row beside the AI summary instead (see cc-footer above). */}
      {!hasCards && <PoweredByNeuract />}

      {/* ASSET RESOLUTION — gated BEFORE Layer 2. Pick → re-run pinned → "resolved" → Open dashboard reveals the cards.
          None of these → terminal (pipeline ends). Dismiss → back to the empty state. (Command view only — the
          inspector is a read-only surface and must never trap the resolution popup over it.) */}
      {view === "command" && resolving && result && (
        <AssetResolution
          candidates={result.asset.candidates}
          noDataAsset={(result.asset_no_data || result.validation_blocked) ? (result.asset?.asset ?? null) : null}
          blockKind={result.validation_blocked ? "validation" : "no_data"}
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

// POWERED BY NEURACT — quiet brand badge pinned to the viewport's bottom-right corner. "powered by" in the muted
// chrome sans; the neuract mark (inline SVG, fills currentColor) + the NEURACT wordmark set in Aeromono (the ONLY
// place that font is used). Purely decorative (pointer-events:none) so it never steals a card interaction.
function PoweredByNeuract({ inline = false }: { inline?: boolean }) {
  return (
    <div className={inline ? "cc-powered cc-powered-inline" : "cc-powered"} aria-label="powered by Neuract">
      <span className="cc-powered-by">powered by</span>
      <svg className="cc-powered-logo" viewBox="0 0 184 180" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path fillRule="evenodd" clipRule="evenodd" d="M0.0200043 50.75L0.0390015 101.5L3.59801 97.255C6.36001 93.962 8.413 92.645 12.757 91.382C19.554 89.406 28.376 89.972 33.757 92.729C37.362 94.575 44.419 102.813 52.837 115C57.335 121.513 80.973 153.995 92.316 169.25L100.308 180H120.777C140.116 180 141.171 179.904 139.899 178.25C139.159 177.288 136.946 174.475 134.981 172C133.017 169.525 130.575 166.15 129.555 164.5C128.535 162.85 125.745 159.025 123.355 156C120.965 152.975 114.256 143.975 108.447 136C102.639 128.025 94.649 117.098 90.693 111.717C80.692 98.114 68.94 82.016 59.5 68.987C55.1 62.915 49.364 55.146 46.753 51.723C44.143 48.3 40.135 42.8 37.848 39.5C33.431 33.128 27.9 25.552 16.125 9.75L8.86 0H4.42999H0L0.0200043 50.75ZM47.328 5.75C59.719 22.222 66.854 31.858 70.04 36.425C71.987 39.216 76.037 44.713 79.04 48.641C82.043 52.568 88.325 61.06 93 67.511C105.491 84.749 125.541 112.249 139.312 131.031C144.365 137.924 151.65 147.96 155.5 153.335C159.35 158.709 165.377 166.908 168.893 171.553C175.193 179.878 175.348 180 179.643 180H184V129.333V78.667L180.25 82.465C172.33 90.488 161.825 92.262 151.929 87.25C145.323 83.904 139.048 76.119 106.992 31.5C102.645 25.45 95.68 15.887 91.513 10.25L83.937 0H63.469H43.002L47.328 5.75ZM140.086 3.11501C122.181 12.062 118.749 35.802 133.263 50.316C147.464 64.517 171.795 60.381 180.661 42.26C186.429 30.47 183.424 15.944 173.388 7.11099C167.768 2.16299 161.559 0 152.982 0C147.525 0 145.191 0.564005 140.086 3.11501ZM18.192 124.144C-0.205999 131.212 -5.254 156.841 8.953 171.048C23.75 185.845 48.553 181.448 57.172 162.5C60.421 155.356 60.37 145.28 57.05 138.526C53.682 131.675 47.399 125.665 41.504 123.656C34.865 121.394 24.801 121.604 18.192 124.144Z" fill="currentColor"/>
      </svg>
      <span className="cc-powered-mark">NEURACT</span>
    </div>
  );
}

// "Copilot running" — the design's last-run confirmation, driven by the live pipeline call.
function RunningCard({ query }: { query: string }) {
  return (
    <div className="cc-lastrun">
      <span className="spark"><Spark /></span>
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
