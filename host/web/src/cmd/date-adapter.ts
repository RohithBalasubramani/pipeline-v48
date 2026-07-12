// host/web/src/cmd/date-adapter.ts — ATOMIC: translate a CMD_V2 card's date-control emission into the host's
// host date_window vocabulary, and expose the callback props to wire onto a date-navigable component.
//
// ONE concern: the FE→host date_window contract for the per-card interactive re-fetch (CmdCard.onDateChange →
// /api/frame). The panel-overview CMD_V2 cards (EnergyTrendCard, DemandProfileCard, …) expose `onRangeChange(value,
// custom)`; the host backend (`host/exec_cards._date_window_for` → `window_policy._range_start`) resolves a bare RANGE
// TOKEN to concrete start/end, so for a PRESET this adapter emits RANGE-ONLY (no date math in the FE); only a CUSTOM
// window carries start/end. Wired generically in the COMPONENTS tier so no per-family fill is needed.

import type { DateWindow } from "../types";

// CMD_V2 range-option value → host range token (host vocab: today | yesterday | last-7-days | this-month |
// last-month | custom-range; the backend resolver anchors each to site-now).
const RANGE_MAP: Record<string, string> = {
  "today": "today",
  "yesterday": "yesterday",
  "last-7": "last-7-days",
  "last-7-days": "last-7-days",
  "last-30": "last-30-days",
  "last-30-days": "last-30-days",
  "this-week": "this-week",
  "this-month": "this-month",
  "last-month": "last-month",
  "custom": "custom-range",
  "custom-range": "custom-range",
};

function firstOf(o: any, ...keys: string[]): string | undefined {
  for (const k of keys) if (o && o[k]) return String(o[k]);
  return undefined;
}

/** A CMD_V2 range control's emission (value, custom?) → a host date_window. A PRESET emits range-only (the backend
 *  fills start/end + a default bucket); a CUSTOM window carries start/end (ISO). An unknown token passes through
 *  verbatim so a new CMD_V2 range never silently breaks. */
export function rangeToWindow(value: any, custom?: any): DateWindow {
  const token = String(value ?? "").trim();
  const range = RANGE_MAP[token] ?? token;
  if (range === "custom-range" || custom) {
    return {
      range: "custom-range",
      start: firstOf(custom, "start", "startDate", "start_date", "from"),
      end: firstOf(custom, "end", "endDate", "end_date", "to"),
    };
  }
  return { range };
}

/** The date-control callback props to spread onto a COMPONENTS-tier card when it is date-navigable (is_history).
 *  `onRangeChange` is the panel-overview pattern (value, custom); it drives the host per-card re-fetch. Harmless on a
 *  component that does not read it. Returns {} when there is no re-fetch callback (non-history cards). */
export function dateControlProps(onDateChange?: (dw: DateWindow) => void): Record<string, unknown> {
  if (!onDateChange) return {};
  return {
    onRangeChange: (value: any, custom?: any) => onDateChange(rangeToWindow(value, custom)),
  };
}
