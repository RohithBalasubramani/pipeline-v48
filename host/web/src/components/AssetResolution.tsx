import { useEffect, useMemo, useRef, useState } from "react";
import type { Candidate } from "../types";
import { fetchAssets } from "../api";

// Asset-resolution popup (implements Command Center.dc.html's resolution card). 1b couldn't pin ONE asset → the copilot
// asks back. Four states: ambiguous (candidate list) · empty (search the full registry) · terminal (none → pipeline ends)
// · resolved (pinned, building). Light teal scrim, hairline card, brown ✦, Space Mono names, sage has_data dots.
// Wired to the REAL pipeline: candidates = result.asset.candidates; pick → re-run pinned; empty browses GET /api/assets.

type View = "ambiguous" | "empty" | "terminal" | "resolved";
const idOf = (a: Candidate) => (a.mfm_id ?? a.id) as number;

// shared chrome icons (ONE source — components/icons)
import { Spark, XIcon, Mag, Ban, Minus } from "./icons";

export function AssetResolution({
  candidates,
  prompt,
  loading,
  onPick,
  onOpenDashboard,
  onDismiss,
  noDataAsset,
  blockKind = "no_data",
}: {
  candidates: Candidate[];
  prompt: string;
  loading: boolean;            // App is re-running pinned after a pick
  onPick: (mfmId: number | number[]) => void;   // one id → pin; an ARRAY → MULTI-ASSET compare (asset_ids[])
  onOpenDashboard: () => void;
  onDismiss: () => void;
  noDataAsset?: { name?: string; class?: string } | null;   // set when the picker opened because the NAMED asset can't
                                                            // render — show it + alternatives. blockKind picks the message.
  blockKind?: "no_data" | "validation";                     // no_data = empty table · validation = data failed validate
}) {
  // no_data opens the picker too (candidates is empty for it → the "empty"/search view, with the asked asset greyed in
  // the full list). The named-but-empty asset is named in the header; "None of these" → the NoDataNotice terminal.
  const base: View = candidates.length ? "ambiguous" : "empty";
  const [view, setView] = useState<View>(base);
  // ONE selection model: `selected` holds every asset the user has clicked. The Run button fires ONCE — 1 → open that
  // asset, 2+ → compare them (asset_ids[]). Clicking a row NEVER runs; nothing is submitted until Run. [single logic]
  const [selected, setSelected] = useState<Candidate[]>([]);
  const [filter, setFilter] = useState("");
  const [active, setActive] = useState(-1);
  const [hover, setHover] = useState(-1);
  const [allAssets, setAllAssets] = useState<Candidate[]>([]);

  const cardRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // empty / browse → fetch the full asset registry (same shape as candidates)
  useEffect(() => {
    if (base !== "empty") return;
    let alive = true;
    fetchAssets()
      .then((assets) => { if (alive && assets.length) setAllAssets(assets); })
      .catch(() => { /* leave empty; rows show "no match" */ });
    return () => { alive = false; };
  }, [base]);

  // focus the search (empty) or the card (for keyboard nav) on view change
  useEffect(() => {
    const t = window.setTimeout(() => {
      if (view === "empty") searchRef.current?.focus();
      else if (view === "ambiguous") cardRef.current?.focus();
    }, 50);
    return () => window.clearTimeout(t);
  }, [view]);

  const rows = useMemo<Candidate[]>(() => {
    if (view === "empty") {
      const f = filter.trim().toLowerCase();
      return allAssets.filter((a) => !f || `${a.name ?? ""} ${a.class ?? ""} ${a.load_group ?? ""}`.toLowerCase().includes(f));
    }
    return candidates;
  }, [view, filter, allAssets, candidates]);

  // click a row → TOGGLE it in/out of the selection (data-bearing only, never while a run is in flight). Nothing runs.
  const isSel = (a: Candidate) => selected.some((x) => idOf(x) === idOf(a));
  const toggle = (a: Candidate | undefined) => {
    if (!a || !a.has_data || loading) return;
    setSelected((s) => (isSel(a) ? s.filter((x) => idOf(x) !== idOf(a)) : [...s, a]));
  };
  // the ONE submit: fires exactly once. 1 selected → open that asset (asset_id); 2+ → compare (asset_ids[]). Disabled
  // while loading so a click can't stack a second pipeline run on the backend.
  const runSelection = () => {
    if (!selected.length || loading) return;
    setView("resolved");
    onPick(selected.length === 1 ? idOf(selected[0]) : selected.map(idOf));
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, rows.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === " ") { e.preventDefault(); toggle(rows[active]); }   // Space toggles the active row into the selection
    else if (e.key === "Enter") { e.preventDefault(); runSelection(); }     // Enter runs the current selection (once)
    else if (e.key === "Escape") { e.preventDefault(); onDismiss(); }
  };

  const echo = prompt.trim();

  const renderRow = (a: Candidate, i: number) => {
    const disabled = !a.has_data;
    const sel = isSel(a);
    const isActive = (i === active || i === hover) && !disabled;
    return (
      <div
        key={`${idOf(a)}-${i}`}
        className="cc-ar-row"
        style={{ background: sel ? "var(--brown-100)" : (isActive ? "var(--brown-050, #f3ece3)" : "transparent"),
                 opacity: disabled ? 0.62 : 1, cursor: disabled ? "default" : "pointer" }}
        onClick={() => toggle(a)}
        onMouseEnter={() => { if (!disabled) setHover(i); }}
        onMouseLeave={() => setHover(-1)}
      >
        {/* the selection checkbox mirrors the row's selected state; clicking anywhere on the row toggles it. */}
        <input
          type="checkbox"
          checked={sel}
          disabled={disabled}
          onClick={(e) => e.stopPropagation()}
          onChange={() => toggle(a)}
          title="Select"
          style={{ marginRight: 10, accentColor: "var(--brown-600)", cursor: disabled ? "default" : "pointer" }}
        />
        <span className="cc-ar-dot" style={{ background: a.has_data ? "var(--sage-400)" : "transparent", border: a.has_data ? "none" : "1.5px solid var(--slate-soft)" }} />
        <div className="cc-ar-rowmid">
          <div className="cc-ar-name" style={{ color: disabled ? "var(--slate-soft)" : "var(--teal-900)" }}>{a.name || `#${idOf(a)}`}</div>
          <div className="cc-ar-meta" style={{ color: disabled ? "#b4bcc4" : "var(--slate-500)" }}>
            {(a.class as string) || "—"}{a.load_group ? `   ·   ${a.load_group}` : ""}
          </div>
        </div>
        {disabled && <span className="cc-ar-status">NO METER DATA</span>}
        <span className="cc-ar-arrow" style={{ color: isActive ? "var(--brown-600)" : "transparent" }}>↵</span>
      </div>
    );
  };

  const footer = (
    <>
      {selected.length > 0 && (
        // THE ONE submit — label adapts: 1 selected → open that asset, 2+ → compare. Disabled while a run is in flight.
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px 2px", minWidth: 0 }}>
          {/* the button NEVER shrinks or wraps (flex row squeezed it → 2-line clip inside the fixed 38px height);
              the selected-names list is the flexible part and truncates with an ellipsis instead. */}
          <button className="cc-ar-btn" style={{ flex: "none", whiteSpace: "nowrap" }}
                  disabled={loading} onClick={runSelection}
                  title={selected.map((a) => a.name).filter(Boolean).join(" · ")}>
            {selected.length === 1
              ? "Open asset"
              : `Compare ${selected.length} assets`}
          </button>
          <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--slate-500)", flex: 1, minWidth: 0,
                         overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {selected.map((a) => a.name).filter(Boolean).join(" · ")}
          </span>
        </div>
      )}
      <div className="cc-ar-rule" />
      <div className="cc-ar-foot">
        <button className="cc-ar-none" onClick={() => setView("terminal")}><Ban />None of these</button>
        <div className="cc-ar-keys"><span>click select</span><span>↵ run</span><span>esc dismiss</span></div>
      </div>
    </>
  );

  return (
    <div className="cc-ar-backdrop" onClick={onDismiss}>
      <div
        ref={cardRef}
        tabIndex={0}
        className={"cc-ar-card" + (view === "terminal" ? " terminal" : "")}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={onKey}
      >
        {view === "ambiguous" && (
          <>
            <div className="cc-ar-head">
              <div className="cc-ar-titlerow">
                <span className="cc-ar-spark"><Spark size={17} /></span>
                <div className="cc-ar-title">WHICH ASSET?</div>
                <button className="cc-ar-x" onClick={onDismiss} aria-label="Dismiss"><XIcon /></button>
              </div>
              <div className="cc-ar-sub"><span className="cc-ar-echo">"{echo}"</span> matches {candidates.length} assets — click to select one (or several to compare), then Run.</div>
            </div>
            <div className="cc-ar-rule" />
            <div className="cc-ar-list">{candidates.map(renderRow)}</div>
            {footer}
          </>
        )}

        {view === "empty" && (
          <>
            <div className="cc-ar-head tight">
              <div className="cc-ar-titlerow">
                <span className="cc-ar-spark"><Spark size={17} /></span>
                <div className="cc-ar-title">{noDataAsset ? (blockKind === "validation" ? "CAN'T RENDER THIS PAGE" : "NO METER DATA") : "NO ASSET IDENTIFIED"}</div>
                <button className="cc-ar-x" onClick={onDismiss} aria-label="Dismiss"><XIcon /></button>
              </div>
              <div className="cc-ar-sub">
                {noDataAsset
                  ? (blockKind === "validation"
                      ? <><span className="cc-ar-echo">{noDataAsset.name ?? "That asset"}</span>'s data didn't pass validation for this page. Pick another asset below.</>
                      : <><span className="cc-ar-echo">{noDataAsset.name ?? "That asset"}</span> has no meter readings yet (never-wired / not logging). Pick another asset below.</>)
                  : <>Couldn't find an asset in <span className="cc-ar-echo">"{echo}"</span>. Search all assets below.</>}
              </div>
            </div>
            <div className="cc-ar-searchwrap">
              <div className="cc-ar-search">
                <span className="ico"><Mag /></span>
                <input ref={searchRef} value={filter} onChange={(e) => { setFilter(e.target.value); setActive(-1); }} onKeyDown={onKey} placeholder="Search all assets" />
              </div>
            </div>
            <div className="cc-ar-list">
              {rows.map(renderRow)}
              {!rows.length && <div style={{ padding: 18, textAlign: "center", color: "var(--slate-soft)", fontFamily: "var(--font-sans)", fontSize: 13 }}>no match</div>}
            </div>
            {footer}
          </>
        )}

        {view === "terminal" && (
          <div className="cc-ar-term">
            <div className="cc-ar-term-icon"><Minus /></div>
            <div className="cc-ar-term-title">{noDataAsset
              ? (blockKind === "validation" ? `${noDataAsset.name ?? "This asset"} can't render this page` : `No live data for ${noDataAsset.name ?? "this asset"}`)
              : "No dashboard built"}</div>
            <div className="cc-ar-term-sub">{noDataAsset
              ? (blockKind === "validation"
                  ? "This asset's data didn't pass validation for the requested page (missing or empty required columns). Pick another asset or refine the command."
                  : "This meter is in the registry but has no readings yet (never-wired or not currently logging). There's nothing to render — pick another asset or refine the command.")
              : "The pipeline stopped without pinning an asset. Refine the command above and try again."}</div>
            <button className="cc-ar-btn" style={{ marginTop: 24 }} onClick={onDismiss}>Refine command</button>
          </div>
        )}

        {view === "resolved" && (
          <>
            <div className="cc-ar-resolved">
              <div className="cc-ar-titlerow">
                <span className="cc-ar-spark"><Spark size={17} /></span>
                {/* the build view shows ALL selected assets (1 → open, 2+ → compare). */}
                <div className="cc-ar-title">{selected.length >= 2 ? `COMPARING ${selected.length} ASSETS` : "ASSET RESOLVED"}</div>
              </div>
              {(selected.length ? selected : []).map((a) => (
                <div className="cc-ar-resolved-row" key={idOf(a)}>
                  <span className="cc-ar-resolved-dot" />
                  <div>
                    <div className="cc-ar-resolved-name">{a.name || `#${idOf(a)}`}</div>
                    <div className="cc-ar-resolved-meta">{(a.class as string) || ""}{a.load_group ? `  ·  ${a.load_group}` : ""}</div>
                  </div>
                </div>
              ))}
              <div className="cc-ar-resolved-note">
                {loading && <span className="spinner" />}
                {loading
                  ? (selected.length >= 2 ? `Building compare · ${selected.length} assets…` : "Pinned · building real-time view…")
                  : (selected.length >= 2 ? "Compare ready" : "Pinned · real-time view ready")}
              </div>
            </div>
            <div className="cc-ar-rule" />
            <div className="cc-ar-btnrow">
              <button className="cc-ar-btn" disabled={loading} onClick={onOpenDashboard}>{loading ? "Building…" : "Open dashboard"}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
