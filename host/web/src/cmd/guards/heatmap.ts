// guards/heatmap.ts — g10 RTM heatmap section contract (split F12, 2026-07-12).
import { isDict, DASH } from "./_shared";

// ── g10: RTM heatmap section contract — {feeders:[{id,…}], totalKw|totalKvar}. The heatmap cell formatter is
// number-only (`value.toFixed(2)` for pf) so a fully-unmeasured feeder row CANNOT render; omit it (per-leaf honesty:
// an all-blank sample = an empty section grid, never a fabricated number, never a crash). Identity/chrome keys
// (id/label/…) don't count as measurements.
const FEEDER_IDENTITY = /(id|label|shortlabel|name|color|statuses)$/i;
export function fixHeatmapSection(d: Record<string, any>): void {
  if (!Array.isArray(d.feeders) || !("totalKw" in d || "totalKvar" in d)) return;
  d.feeders = d.feeders.filter((f: any) => {
    if (!isDict(f)) return true;
    return Object.entries(f).some(
      ([k, v]) => !FEEDER_IDENTITY.test(k) && !(v == null || v === "" || v === DASH),
    );
  });
}
