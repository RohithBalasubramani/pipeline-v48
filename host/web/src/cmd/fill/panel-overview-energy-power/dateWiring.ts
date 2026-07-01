// Control wiring → host date-window re-fetch, for the panel-overview/energy-power cards.
import type {
  EnergySamplingOption,
  EnergyShiftOption,
  EnergyTrendRangeOption,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/config";
import type { DateWindow } from "./types";

/* ── Control wiring → host date-window re-fetch ───────────────────────────────
 * Each card owns its date control (a SamplingPicker, surfaced to the card body
 * as the controlled `onRangeChange` / `onSamplingChange` pair, OR — for the
 * equipment-detail chart — a `onPeriodChange` period-string callback). Wiring =
 * translate the control's emitted value into the host `DateWindow`
 * ({range, sampling, start?, end?}) and call `onDateChange`, which makes the
 * host re-fetch JUST this card's ems_backend frame for that window.
 *
 * ems_backend window vocabulary (host/src/types.ts → DateWindow):
 *   range    ∈ today | yesterday | last-7-days | this-month | custom-range
 *   sampling ∈ hourly | 2hour | shift | day | week
 */

/** EnergyTrendRangeOption (today|yesterday|last-7|this-month|last-month) →
 *  ems_backend `range`. `last-7` is the picker's multi-day default; `last-month`
 *  has no ems slot so it folds onto `this-month` (nearest monthly bucket). */
export function trendRangeToWindowRange(range: EnergyTrendRangeOption): string {
  switch (range) {
    case "today":      return "today";
    case "yesterday":  return "yesterday";
    case "last-7":     return "last-7-days";
    case "this-month": return "this-month";
    case "last-month": return "this-month";
    default:           return "last-7-days";
  }
}

/** EnergySamplingOption (hourly|shift) → ems_backend `sampling`. */
export function samplingToWindowSampling(sampling: EnergySamplingOption): string {
  return sampling === "shift" ? "shift" : "hourly";
}

/** Card 40's period STRING (one of data.periodOptions, e.g. "today" / "this
 *  week" / "this month") → ems_backend `range`. Mirrors the chart's own
 *  EP_PERIOD_PRESETS (today / last-7-days / this-month). */
export function periodStringToWindowRange(period: string): string {
  const p = String(period || "").toLowerCase();
  if (p.includes("week")) return "last-7-days";
  if (p.includes("month")) return "this-month";
  if (p.includes("yesterday")) return "yesterday";
  return "today";
}

/** Build a per-card control binder. The SamplingPicker surfaces its committed
 *  selection as TWO synchronous callbacks (`onRangeChange` then
 *  `onSamplingChange`) inside one Apply. Both feed this binder, which merges
 *  them and flushes ONE `onDateChange({range, sampling})` on a microtask so the
 *  host re-fetches once per Apply (not twice). onDateChange is optional-guarded
 *  so an older host call path (no 3rd arg) is a no-op. */
export function makeWindowBinder(
  onDateChange: ((dw: DateWindow) => void) | undefined,
  seed: { range: string; sampling: string },
) {
  let pending: DateWindow | null = null;
  const flush = () => {
    const dw = pending;
    pending = null;
    if (dw && onDateChange) onDateChange(dw);
  };
  const stage = (patch: DateWindow) => {
    if (!pending) {
      pending = { range: seed.range, sampling: seed.sampling };
      queueMicrotask(flush);
    }
    Object.assign(pending, patch);
  };
  return {
    onRangeChange: (value: EnergyTrendRangeOption) =>
      stage({ range: trendRangeToWindowRange(value) }),
    onSamplingChange: (value: { sampling: EnergySamplingOption; shift: EnergyShiftOption }) =>
      stage({ sampling: samplingToWindowSampling(value.sampling) }),
  };
}
