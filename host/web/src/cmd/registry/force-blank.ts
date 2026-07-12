// registry/force-blank.ts — NO-SEED-LEAK force-blank [VC-01/02] (split F11, 2026-07-12).

// ── NO-SEED-LEAK force-blank [VC-01/02] ──────────────────────────────────────────────────────────────────────────
// Split a dotted/bracketed path ('config.rows[2].value') into segments so a leaf can be force-blanked in the payload.
function segs(path: string): (string | number)[] {
  const out: (string | number)[] = [];
  for (const m of path.matchAll(/([^.[\]]+)|\[(\d+)\]/g)) out.push(m[2] !== undefined ? Number(m[2]) : m[1]);
  return out;
}
// Return a DEEP-CLONED payload with each `paths` leaf set to null. Defensive: the host already blanks these server-side,
// but the FE re-asserts it so a numeric that equals its seed with no live provenance can NEVER slip through. Never
// mutates the source payload.
export function forceBlank(payload: any, paths?: string[]): any {
  if (!paths || !paths.length || !payload || typeof payload !== "object") return payload;
  let clone: any;
  try { clone = structuredClone(payload); } catch { clone = JSON.parse(JSON.stringify(payload)); }
  for (const p of paths) {
    const s = segs(p);
    let cur = clone;
    let ok = true;
    for (let i = 0; i < s.length - 1; i++) { if (cur == null) { ok = false; break; } cur = cur[s[i]]; }
    if (ok && cur != null && typeof cur === "object") {
      const k = s[s.length - 1];
      const existing = cur[k];
      // TYPE-PRESERVING blank: array stays [] (mapper .map()/.filter() render empty, never crash on null), object stays
      // {}, scalar → null (→ "—"). Fixes "Cannot read properties of null (reading 'map')". [NO-SEED-LEAK + no-crash]
      cur[k] = Array.isArray(existing) ? [] : (existing != null && typeof existing === "object" ? {} : null);
    }
  }
  return clone;
}
