// guards/no-assert.ts — g7 no-assert driver fallback (split F12, 2026-07-12).
import { DASH } from "./_shared";

// ── g7: 'OK' as the driver fallback asserts health for an unmatched/unmeasured driver — the no-assert dash instead.
export function fixNoAssertFallback(d: Record<string, any>): void {
  if (typeof d.driverFallbackCode === "string" && d.driverFallbackCode !== DASH) d.driverFallbackCode = DASH;
}
