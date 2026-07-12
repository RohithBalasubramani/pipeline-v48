// guards/zero-row.ts — g16 zero-row plot → the component OWN loading skeleton; ROOT-LEVEL prop seam, called from
// guardPayload before walk (split F12, 2026-07-12).
import { isDict, finite } from "./_shared";

// ── g16: zero-row plot → the component's OWN socket-loading skeleton (see header). Root-level only: `loading` is a
// component PROP (sibling of the vm key), so the rule runs once on the payload root in guardPayload, never in walk.
function hasFiniteLeaf(node: any): boolean {
  if (finite(node)) return true;
  if (Array.isArray(node)) return node.some(hasFiniteLeaf);
  if (isDict(node)) return Object.values(node).some(hasFiniteLeaf);
  return false;
}
const axisDomainShaped = (v: any) => isDict(v) && Array.isArray(v.ticks) && "max" in v && "min" in v;
export function fixEmptyPlotLoading(root: Record<string, any>): void {
  if (root.loading != null) return;
  for (const vm of [root, ...Object.values(root)]) {
    if (!isDict(vm)) continue;
    const zeroRow = Object.entries(vm).some(([k, v]) => /points$/i.test(k) && Array.isArray(v) && v.length === 0);
    if (zeroRow && Object.values(vm).some(axisDomainShaped) && !hasFiniteLeaf(vm)) {
      root.loading = true;
      return;
    }
  }
}
