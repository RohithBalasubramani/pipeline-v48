// guards/sankey.ts — g8 sankey contract (split F12, 2026-07-12).
import { isDict, finite } from "./_shared";

// ── g8: sankey contract — drop unmeasured (non-finite) links; if NOTHING is measured, clear nodes too so the
// primitive's own `nodes.length===0` empty state renders. A non-finite 'layer' on ANY node poisons d3's column
// packing (NaN column index → sparse columns → `column.sort` throws) → drop 'layer' from every node and let d3's own
// justify align by link depth (dense, gap-free).
export function fixSankey(s: Record<string, any>): void {
  if (!Array.isArray(s.nodes) || !Array.isArray(s.links)) return;
  if (!s.links.length || !s.links.every((l: any) => isDict(l) && "source" in l && "target" in l)) return;
  const kept = s.links.filter((l: any) => finite(l.value));
  if (kept.length !== s.links.length) {
    s.links = kept;
    if (!kept.length) s.nodes = [];
  }
  let relayer = s.nodes.some((n: any) => isDict(n) && "layer" in n && !finite(n.layer));
  if (!relayer && s.links.length) {
    // DEGENERATE layers: a link's endpoints can never share a layer in a real flow (d3 packs columns from these and
    // a same-layer link leaves whole columns empty → `column.sort` throws). Blanked/zeroed layer writes look exactly
    // like this (every node layer 0).
    const layerOf = new Map(s.nodes.filter(isDict).map((n: any) => [n.id, n.layer]));
    relayer = s.links.some((l: any) => {
      const a = layerOf.get(l.source), b = layerOf.get(l.target);
      return finite(a) && finite(b) && a === b;
    });
  }
  if (relayer && s.links.length) {
    // RECOMPUTE layers from the measured link topology (longest-path — the same layering d3's own depth pass uses).
    // Pure structure derived from the payload's own links: no value invented. Isolated nodes sit at layer 0;
    // FlowSankey dense-packs whatever set results, so columns are always gap-free.
    const depth = new Map<string, number>(s.nodes.filter(isDict).map((n: any) => [n.id, 0]));
    for (let i = 0; i <= s.links.length; i++) {
      let changed = false;
      for (const l of s.links) {
        const d = (depth.get(l.source) ?? 0) + 1;
        if (d > (depth.get(l.target) ?? 0)) {
          depth.set(l.target, d);
          changed = true;
        }
      }
      if (!changed) break;
    }
    for (const n of s.nodes) if (isDict(n)) n.layer = depth.get(n.id) ?? 0;
  }
}
