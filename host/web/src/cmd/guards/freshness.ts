// guards/freshness.ts — g1 freshness view-model contract (split F12, 2026-07-12).
import { blank, DASH } from "./_shared";

// ── g1: freshness view-model contract ({status,label,tone,lastUpdateLabel}) — LiveTag→StatusBadge consumer.
// StatusBadge's own documented blank is `<StatusBadge label="—" tone="neutral"/>` (grey, no asserted state).
export function fixFreshness(d: Record<string, any>): boolean {
  if (!("lastUpdateLabel" in d) || !("status" in d) || !("tone" in d)) return false;
  if (blank(d.tone)) d.tone = "neutral";
  if (blank(d.status)) d.status = "unknown";
  if (blank(d.label)) d.label = DASH;
  return true;
}
