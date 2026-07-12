// guards/rehydrate.ts — g4 sibling-homogeneous null-object rehydrate (split F12, 2026-07-12).
import { isDict, DASH } from "./_shared";

// ── g4: sibling-homogeneous null-object rehydrate — stats.worstVThd:null beside stats.worstIThd:{...} (same length,
// same 'worst' prefix). The STRUCTURE is chrome the component derefs unconditionally (stats.worstVThd.vThd); every
// scalar leaf is '—' (blank), arrays [], nested dicts recursed — no value asserted.
function commonPrefixLen(a: string, b: string): number {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return i;
}
function blankClone(src: any): any {
  if (Array.isArray(src)) return [];
  if (isDict(src)) {
    const out: Record<string, any> = {};
    for (const [k, v] of Object.entries(src)) out[k] = isDict(v) || Array.isArray(v) ? blankClone(v) : DASH;
    return out;
  }
  return DASH;
}
export function rehydrateSiblingObjects(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (v !== null) continue;
    for (const [k2, v2] of Object.entries(d)) {
      if (k2 === k || k2.length !== k.length || !isDict(v2) || Object.keys(v2).length < 3) continue;
      if (commonPrefixLen(k, k2) >= 4) {
        d[k] = blankClone(v2);
        break;
      }
    }
  }
}
