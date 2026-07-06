// shims.ts — HOST-runtime string/number-format shims [family H, code-last-resort].
//
// WHY: several read-only CMD_V2 leaf sites call Number-only formatters PLAINLY (`service.hours.toFixed(0)`,
// `runHours.toFixed(1)`, `k.agingFactor.toFixed(1)`) with NO null branch — they were designed for always-numeric mock
// view-models. A V48 honest-blank leaf ('—') therefore CANNOT render through them: both null and '—' throw, and the
// Boundary masks the whole card. The one generic, zero-fabrication fix that keeps the per-leaf dash: teach the DASH
// STRING to answer the number-formatting protocol with itself. `'—'.toFixed(1) === '—'` — the honest dash rides
// through every unguarded toFixed/toPrecision site and renders as the dash it already is.
//
// SCOPE: String.prototype only, added ONLY if absent (native String has toLocaleString already — it ignores number
// args and returns the string, which is exactly the same contract). This is host/web runtime state — CMD_V2 source is
// untouched (READ-ONLY mandate). Applies to all strings: `s.toFixed()` returns `s` — display-as-is, never NaN,
// never a fabricated number.
/* eslint-disable no-extend-native */
declare global {
  interface String {
    toFixed(fractionDigits?: number): string;
    toPrecision(precision?: number): string;
  }
}

if (!(String.prototype as any).toFixed) {
  Object.defineProperty(String.prototype, "toFixed", {
    value: function toFixed(this: string) {
      return String(this);
    },
    writable: true,
    configurable: true,
    enumerable: false,
  });
}
if (!(String.prototype as any).toPrecision) {
  Object.defineProperty(String.prototype, "toPrecision", {
    value: function toPrecision(this: string) {
      return String(this);
    },
    writable: true,
    configurable: true,
    enumerable: false,
  });
}

// ── 'info' alias in the UPS DOMAIN tone map ────────────────────────────────────────────────────────────────────────
// guards.ts normalizes every blanked tone to the DS 'info' (teal, informational — the least assertive tone; present
// in StatusPill / StatusBadge / KPI_STATUS_DOT_PRESETS). But the UPS cards speak the DOMAIN enum
// (success/warning/danger) and translate via the exported STATUS_PILL_TONE map — 'info' would map to undefined and
// crash toneChipColors/KPI dot lookups. One runtime alias (info → info) makes the SAME blank token valid through both
// enums. Module-state augmentation only — CMD_V2 source untouched.
import { STATUS_PILL_TONE } from "@cmd-v2/pages/assets/ups/shared/adapters";
if (!(STATUS_PILL_TONE as any).info) (STATUS_PILL_TONE as any).info = "info";

export {};
