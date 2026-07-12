// prim/health-history.tsx — Voltage/Current health + history family on PRIMITIVES ONLY. [primitives-only port]
//
// Owns the HealthSummaryPanel-class cards (43/45 feeder, 66/68 DG) and the HistoryPanel-class cards (44/46 feeder,
// 67/69 DG). renderCmd routes by `render_card_id ?? card_id`, so a feeder card 44 emitted in the unified history
// shape (render_card_id 67) and a DG card 67 both land on the same HistoryPanel renderer — hence one renderer per
// class, keyed under every id in the class. The two panel reimplementations live in ./hh-health + ./hh-history
// (barrel-only, one concern per file); this file is the registry + payload adapters + the SamplingPicker↔host
// date-control wiring (the seam the old feeder/DG fills injected via withDateControl — a function can't ride JSON).
import React from "react";
import { presetRange } from "@cmd-v2/components/charts/primitives";
import type { DateWindow } from "../../types";
import { HealthCard } from "./hh-health";
import { HistoryPanel } from "./hh-history";

// ── SamplingPicker → host date_window (reimplements fill/shared/sampling-window.ts) ───────────────────────────────
/** Committed default so the picker renders: Today + the 2hour grid the detail tabs use. */
function defaultSampling(): any {
  return { preset: "today", range: presetRange("today", new Date()), resolution: "2hour" };
}
/** Committed SamplingSelection → host date_window. range tokens stay in the host PresetId vocabulary; last-month
 *  (no host token) + custom fall to an explicit [start,end] window; the picked resolution rides as `sampling`. */
function samplingToWindow(sel: any): DateWindow {
  const range = sel?.range ?? null;
  const chosen = sel?.resolution; // 2hour | shift | day | week, or undefined
  const custom = (sampling: string): DateWindow => ({ range: "custom-range", sampling: chosen ?? sampling, start: range?.start ?? undefined, end: range?.end ?? undefined });
  switch (sel?.preset) {
    case "yesterday": return { range: "yesterday", sampling: chosen ?? "hourly" };
    case "last-7-days": return { range: "last-7-days", sampling: chosen ?? "day" };
    case "this-month": return { range: "this-month", sampling: chosen ?? "week" };
    case "last-month": return custom("week");
    case "custom": return custom("hourly");
    case "today":
    default: return { range: "today", sampling: chosen ?? "2hour" };
  }
}

// ── wrappers ──────────────────────────────────────────────────────────────────────────────────────────────────────
/** Health cards. Feeder nests the view-model under `payload.health.{data,phaseVariant}`; DG carries it flat as
 *  `payload.data` (no phaseVariant). Extract from whichever is present; default phaseVariant 'rows'. */
function HealthWrapper({ payload }: { payload: any }) {
  const health = payload?.health ?? payload ?? {};
  const data = health?.data ?? {};
  const phaseVariant = health?.phaseVariant === "bars" ? "bars" : "rows";
  return <HealthCard data={data} phaseVariant={phaseVariant} loading={payload?.loading === true} />;
}

/** History cards. `payload.data` = HistoryPanelData (both feeder-44 and DG-67/69); a legacy `payload.history.data`
 *  nesting is honored defensively. The SamplingPicker only mounts when data carries BOTH `sampling` and
 *  `onSamplingChange` — a function can't ride the JSON payload, so we inject them from the host `onDateChange`
 *  here (local committed state drives the controlled picker; Apply fires the host re-fetch). */
function HistoryWrapper({ payload, onDateChange }: { payload: any; onDateChange?: (dw: any) => void }) {
  const base = payload?.data ?? payload?.history?.data ?? {};
  const [sampling, setSampling] = React.useState<any>(() => base?.sampling ?? defaultSampling());
  const data = onDateChange
    ? { ...base, sampling, onSamplingChange: (next: any) => { setSampling(next); onDateChange(samplingToWindow(next)); } }
    : base;
  return <HistoryPanel data={data} loading={payload?.loading === true} />;
}

const HEALTH = (payload: any) => <HealthWrapper payload={payload} />;
const HISTORY = (payload: any, onDateChange?: (dw: any) => void) => <HistoryWrapper payload={payload} onDateChange={onDateChange} />;

export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  43: HEALTH, // Voltage Live Health (feeder)
  45: HEALTH, // Current Live Health (feeder)
  66: HEALTH, // Voltage Live Health (DG)
  68: HEALTH, // Current Live Health (DG)
  44: HISTORY, // Voltage History (feeder; also emitted as render_card_id 67)
  46: HISTORY, // Current History (feeder)
  67: HISTORY, // Voltage History (DG / unified)
  69: HISTORY, // Current History (DG)
};
