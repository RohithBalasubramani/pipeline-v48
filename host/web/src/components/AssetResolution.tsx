import { useEffect, useMemo, useRef, useState } from "react";
import type { Candidate } from "../types";

// Asset-resolution popup (implements Command Center.dc.html's resolution card). 1b couldn't pin ONE asset → the copilot
// asks back. Four states: ambiguous (candidate list) · empty (search the full registry) · terminal (none → pipeline ends)
// · resolved (pinned, building). Light teal scrim, hairline card, brown ✦, Space Mono names, sage has_data dots.
// Wired to the REAL pipeline: candidates = result.asset.candidates; pick → re-run pinned; empty browses GET /api/assets.

type View = "ambiguous" | "empty" | "terminal" | "resolved";
const idOf = (a: Candidate) => (a.mfm_id ?? a.id) as number;

function Spark({ size = 17 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z" />
    </svg>
  );
}
const XIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>
);
const Mag = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
);
const Ban = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><circle cx="12" cy="12" r="9" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
);
const Minus = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><line x1="5" y1="12" x2="19" y2="12" /></svg>
);

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
  onPick: (mfmId: number) => void;
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
  const [picked, setPicked] = useState<Candidate | null>(null);
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
    fetch("/api/assets")
      .then((r) => r.json())
      .then((d) => { if (alive && d.ok && Array.isArray(d.assets)) setAllAssets(d.assets); })
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

  const select = (a: Candidate | undefined) => {
    if (!a || !a.has_data) return;
    setPicked(a);
    setView("resolved");
    onPick(idOf(a));
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, rows.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { select(rows[active]); }
    else if (e.key === "Escape") { e.preventDefault(); onDismiss(); }
  };

  const echo = prompt.trim();

  const renderRow = (a: Candidate, i: number) => {
    const disabled = !a.has_data;
    const isActive = (i === active || i === hover) && !disabled;
    return (
      <div
        key={`${idOf(a)}-${i}`}
        className="cc-ar-row"
        style={{ background: isActive ? "var(--brown-100)" : "transparent", opacity: disabled ? 0.62 : 1, cursor: disabled ? "default" : "pointer" }}
        onClick={() => select(a)}
        onMouseEnter={() => { if (!disabled) setHover(i); }}
        onMouseLeave={() => setHover(-1)}
      >
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
      <div className="cc-ar-rule" />
      <div className="cc-ar-foot">
        <button className="cc-ar-none" onClick={() => setView("terminal")}><Ban />None of these</button>
        <div className="cc-ar-keys"><span>↑↓ navigate</span><span>↵ select</span><span>esc dismiss</span></div>
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
                <span className="cc-ar-spark"><Spark /></span>
                <div className="cc-ar-title">WHICH ASSET?</div>
                <button className="cc-ar-x" onClick={onDismiss} aria-label="Dismiss"><XIcon /></button>
              </div>
              <div className="cc-ar-sub"><span className="cc-ar-echo">"{echo}"</span> matches {candidates.length} assets — pick one.</div>
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
                <span className="cc-ar-spark"><Spark /></span>
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
                <span className="cc-ar-spark"><Spark /></span>
                <div className="cc-ar-title">ASSET RESOLVED</div>
              </div>
              <div className="cc-ar-resolved-row">
                <span className="cc-ar-resolved-dot" />
                <div>
                  <div className="cc-ar-resolved-name">{picked?.name || `#${picked ? idOf(picked) : ""}`}</div>
                  <div className="cc-ar-resolved-meta">{(picked?.class as string) || ""}{picked?.load_group ? `  ·  ${picked.load_group}` : ""}</div>
                </div>
              </div>
              <div className="cc-ar-resolved-note">
                {loading && <span className="spinner" />}
                {loading ? "Pinned · building real-time view…" : "Pinned · real-time view ready"}
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
