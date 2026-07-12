/** admin/bits.tsx — tiny shared pieces: status dot, chips, KV, collapsible JSON block. */
import { useState } from "react";

export const Dot = ({ status }: { status: string }) => <span className={`px-dot ${status}`} />;

export const Chip = ({ tone = "", children }: { tone?: string; children: any }) => (
  <span className={`px-chip ${tone}`}>{children}</span>
);

export const Kv = ({ k, v }: { k: string; v: any }) => (
  <div className="px-kv">
    <span className="k">{k}</span>
    <span className="v">{v === null || v === undefined || v === "" ? "—" : String(v)}</span>
  </div>
);

export const ms = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n >= 10000 ? `${(n / 1000).toFixed(1)}s` : `${Math.round(n)}ms`;

export const tok = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n >= 10000 ? `${(n / 1000).toFixed(1)}k` : String(n);

/** Collapsible pretty-JSON. Collapsed above `fold` chars so a huge payload never freezes the page. */
export function JsonBlock({ value, fold = 1600, label }: { value: any; fold?: number; label?: string }) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 1);
  const [open, setOpen] = useState((text?.length ?? 0) <= fold);
  if (value === null || value === undefined) return <span className="px-muted">—</span>;
  if (!open) {
    return (
      <button className="px-btn ghost" onClick={() => setOpen(true)} style={{ height: 24, fontSize: 11 }}>
        show {label || "JSON"} ({(text.length / 1024).toFixed(1)} KB)
      </button>
    );
  }
  return <pre className="px-json">{text}</pre>;
}
