/** admin/widgets.tsx — shared report widgets: run links, date/search filter fields, bar lists, day sparks,
 *  verdict-mix strips, stat tiles. Single-series marks are teal (labels carry identity); the verdict mix uses the
 *  status trio with 2px gaps and ALWAYS prints counts beside the strip (never color alone). */
import { useState } from "react";
import { navigate, traceHref } from "./router";

export function RunLink({ rid }: { rid: string | null | undefined }) {
  if (!rid) return <span className="px-muted">—</span>;
  return (
    <a className="px-runlink" href={traceHref(rid)}
       onClick={(e) => { e.preventDefault(); navigate(traceHref(rid)); }}>
      {rid}
    </a>
  );
}

export type Window = { from: string; to: string };

/** from/to date fields + optional search box, submitted on Apply (Enter works via form submit). */
export function FilterBar({ win, setWin, q, setQ, qLabel = "search", extra, onApply }: {
  win: Window; setWin: (w: Window) => void;
  q?: string; setQ?: (q: string) => void; qLabel?: string;
  extra?: React.ReactNode; onApply: () => void;
}) {
  const [local, setLocal] = useState(win);
  const [localQ, setLocalQ] = useState(q ?? "");
  return (
    <form className="px-filters" onSubmit={(e) => { e.preventDefault(); setWin(local); setQ?.(localQ); onApply(); }}>
      <div className="px-field"><label>from</label>
        <input type="date" value={local.from} onChange={(e) => setLocal({ ...local, from: e.target.value })} /></div>
      <div className="px-field"><label>to</label>
        <input type="date" value={local.to} onChange={(e) => setLocal({ ...local, to: e.target.value })} /></div>
      {setQ !== undefined && (
        <div className="px-field"><label>{qLabel}</label>
          <input className="wide" value={localQ} placeholder="substring…"
                 onChange={(e) => setLocalQ(e.target.value)} /></div>
      )}
      {extra}
      <button className="px-btn" type="submit">Apply</button>
    </form>
  );
}

export const winQs = (w: Window) =>
  [w.from ? `from=${w.from}` : "", w.to ? `to=${w.to}` : ""].filter(Boolean).join("&");

/** Horizontal bar list — one hue, value labels always printed. */
export function Bars({ rows, err }: { rows: { label: string; value: number; hint?: string }[]; err?: boolean }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (!rows.length) return <div className="px-empty">nothing in this window</div>;
  return (
    <div className="px-bars">
      {rows.map((r) => (
        <div className="px-bar-row" key={r.label} title={r.hint || `${r.label}: ${r.value}`}>
          <span className="lbl">{r.label}</span>
          <span className="track"><span className={`fill${err ? " err" : ""}`} style={{ width: `${(100 * r.value) / max}%` }} /></span>
          <span className="val">{r.value.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

/** Day-bucketed column spark — per-mark native tooltip carries day + exact value. */
export function Spark({ caption, points, fmt = (n) => n.toLocaleString() }: {
  caption: string; points: { day: string; value: number }[]; fmt?: (n: number) => string;
}) {
  const max = Math.max(1, ...points.map((p) => p.value));
  return (
    <div className="px-sparkwrap">
      <div className="cap">{caption}</div>
      {points.length ? (
        <>
          <div className="px-spark">
            {points.map((p) => (
              <div key={p.day} className="col" title={`${p.day}: ${fmt(p.value)}`}
                   style={{ height: `${Math.max(4, (100 * p.value) / max)}%` }} />
            ))}
          </div>
          <div className="axis"><span>{points[0].day}</span><span>{points[points.length - 1].day}</span></div>
        </>
      ) : <div className="px-empty">no data</div>}
    </div>
  );
}

/** render / partial / honest_blank mix — status colors + 2px gaps + counts printed beside. */
export function VerdictMix({ render, partial, blank }: { render?: number | null; partial?: number | null; blank?: number | null }) {
  const r = render ?? 0, p = partial ?? 0, b = blank ?? 0, total = r + p + b;
  if (!total) return <span className="px-muted">—</span>;
  return (
    <span className="px-mix" title={`render ${r} · partial ${p} · honest_blank ${b}`}>
      <span className="strip" style={{ width: 72 }}>
        {r > 0 && <span className="seg render" style={{ width: `${(100 * r) / total}%` }} />}
        {p > 0 && <span className="seg partial" style={{ width: `${(100 * p) / total}%` }} />}
        {b > 0 && <span className="seg honest_blank" style={{ width: `${(100 * b) / total}%` }} />}
      </span>
      <span>{r}·{p}·{b}</span>
    </span>
  );
}

export function Stat({ k, v, sub }: { k: string; v: React.ReactNode; sub?: string }) {
  return (
    <div className="px-stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      {sub ? <div className="sub">{sub}</div> : null}
    </div>
  );
}

export function Loading({ err }: { err?: string | null }) {
  if (err) return <div className="px-error-banner">{err}</div>;
  return <div className="px-loading">loading…</div>;
}
