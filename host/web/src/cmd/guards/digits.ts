// guards/digits.ts — g3 formatter digit-chrome keys (split F12, 2026-07-12).
import { isDict, finite } from "./_shared";

const DIGIT_KEY = /(decimals|digits)$/i;

// ── g3: formatter DIGITS inputs (fmt(value, decimals) → toLocaleString({minimumFractionDigits})) must be numbers —
// a '—'/null digit count is NaN → RangeError. 0 digits = chrome, never a data claim. Handles both the scalar form
// (railDecimals) and the dict form (decimals: {thd, pfLow, pfHigh}).
export function fixDigitChrome(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (!DIGIT_KEY.test(k)) continue;
    if (v === null || (typeof v === "string" && !finite(Number(v)))) d[k] = 0;
    else if (isDict(v)) {
      for (const [ik, iv] of Object.entries(v)) if (!finite(iv)) (v as any)[ik] = 0;
    }
  }
}
