import React from "react";
// FILL module — page "individual-feeder-meter-shell/energy-power".
// Wires each card on the page to its REAL CMD V2 component fed with LIVE ems_backend data, by REUSING the page's own
// CMD V2 mapper (mapEnergyPowerSocketsToSnapshot) + view-model (createEnergyPowerViewModel) — NEVER re-implementing a
// transform. Honest-degrade: a missing/unmappable frame falls back to the card's byte-identical default payload.
//
// Cards (from /tmp/fill_manifest.json):
//   39 — TodaysEnergyCard   (top-left)   ← view-model `.todaysEnergy`   (LIVE energy-power socket scalars + config)
//   42 — LoadAnomaliesChart (bottom-right)← view-model `.loadAnomalies`  (HISTORY energy-power-history buckets/KPIs)
//
// The host feeds ONE ems_backend frame per card (frames[card.endpoint]). The page mapper, however, consumes TWO
// sockets (live `energy-power` + history `energy-power-history`). So we detect which kind of frame we got (history
// frames carry `buckets`/`kpis`; live frames carry `queue`/`columns`), reduce it into the matching reducer state via
// CMD V2's OWN pure reducers, and present BOTH socket adapters to the mapper — the absent side stays in its idle
// (pre-snapshot) state, which the mapper/view-model already degrade gracefully (FE-1 placeholder branch).

import {
  LoadAnomaliesChart,
  TodaysEnergyCard,
} from "@cmd-v2/components/charts/primitives";
import {
  createEnergyPowerViewModel,
} from "@cmd-v2/pages/electrical/tabs/energy-power/energyPowerViewModel";
import {
  mapEnergyPowerSocketsToSnapshot,
  type LiveSocketLike,
  type HistorySocketLike,
} from "@cmd-v2/pages/electrical/tabs/energy-power/energyPowerMapper";
import {
  createInitialColumnRowState,
  reduceColumnRowFrame,
} from "@cmd-v2/realtime/columnRowReducer";
import {
  createInitialHistoryState,
  reduceHistoryFrame,
} from "@cmd-v2/realtime/historyFrameReducer";
import type {
  EnergyPowerTabData,
  LoadAnomaliesData,
  TodaysEnergyData,
} from "@cmd-v2/pages/electrical/tabs/energy-power/energyPowerTypes";

// ── frame plumbing ──────────────────────────────────────────────────────────
// fetch_frame returns the LATEST ems_backend snapshot dict (type "snapshot" or omitted). The CMD V2 reducers branch on
// `frame.type === 'snapshot'`, so normalise a missing type to "snapshot" before reducing.
function normalizeFrame(frame: any): any {
  if (!frame || typeof frame !== "object") return null;
  return frame.type ? frame : { ...frame, type: "snapshot" };
}

const isHistoryFrame = (f: any): boolean => !!f && (Array.isArray(f.buckets) || f.kpis != null);
const isLiveFrame = (f: any): boolean => !!f && (Array.isArray(f.queue) || Array.isArray(f.columns));

// Build a LiveSocketLike from a column-row frame (or an idle adapter when none was supplied).
function liveSocketFrom(frame: any): LiveSocketLike {
  let state = createInitialColumnRowState();
  if (frame) {
    try { state = reduceColumnRowFrame(state, frame); } catch { /* keep initial */ }
  }
  return { state, status: state.hasSnapshot ? "open" : "idle" };
}

// Build a HistorySocketLike from a history frame (or an idle adapter when none was supplied).
function historySocketFrom(frame: any): HistorySocketLike {
  let state = createInitialHistoryState();
  if (frame) {
    try { state = reduceHistoryFrame(state, frame); } catch { /* keep initial */ }
  }
  return { state, status: state.hasSnapshot ? "open" : "idle" };
}

// Reuse the page's REAL mapper + view-model to turn whatever frame we have into the panel-ready EnergyPowerTabData.
// Returns null when the frame yields nothing mappable (mapper returns null pre-snapshot) so the caller degrades.
function buildViewModel(frame: any): EnergyPowerTabData | null {
  const f = normalizeFrame(frame);
  if (!f) return null;
  const liveFrame = isLiveFrame(f) ? f : null;
  const histFrame = isHistoryFrame(f) ? f : null;
  if (!liveFrame && !histFrame) return null;
  const snapshot = mapEnergyPowerSocketsToSnapshot({
    socket: liveSocketFrom(liveFrame),
    historySocket: historySocketFrom(histFrame),
    config: null,
  });
  if (!snapshot) return null;
  return createEnergyPowerViewModel(snapshot);
}

// ── period → date_window mapping ─────────────────────────────────────────────
// Both cards' header controls (TodaysEnergyCard's FilterPillSelect, LoadAnomaliesChart's PeriodSelect) emit a single
// `period` LABEL string drawn from `periodOptions`. Across the page these labels appear as `Today / This Week /
// This Month` (the live `energyPowerMapper` vocabulary) and `Today / Weekly / Monthly / Quarterly` (the mock template),
// so we match on lower-cased substrings — exactly mirroring CMD V2's own `energyPowerHistoryParamsForPeriod()` in
// energyPowerConfig.ts. We translate each period into the ems_backend window vocabulary the host re-fetches against:
//   range    ∈ today | yesterday | last-7-days | this-month | custom-range
//   sampling ∈ hourly | 2hour | shift | day | week   (see ems_backend SAMPLING_BY_RANGE / _SAMPLING_ALIASES)
// `Today` keeps the detail-tab default {today, 2hour} (12 two-hour buckets); week/month roll up to {…, day}.
function periodToDateWindow(period: string): { range: string; sampling: string } {
  const p = (period ?? "").toLowerCase();
  if (p.includes("week"))    return { range: "last-7-days", sampling: "day" };   // "This Week" / "Weekly"
  if (p.includes("month"))   return { range: "this-month",  sampling: "day" };   // "This Month" / "Monthly"
  if (p.includes("quarter")) return { range: "this-month",  sampling: "week" };  // "Quarterly" → monthly window, weekly buckets
  if (p.includes("yester"))  return { range: "yesterday",   sampling: "2hour" }; // "Yesterday"
  return { range: "today", sampling: "2hour" };                                  // "Today" (default) + unknown labels
}

// ── payload unwrap ───────────────────────────────────────────────────────────
// exact_metadata = the Storybook story ARGS: `{ data: <card-data>, variant }`. The real card prop sits under `data`
// (see EnergyPowerCards.stories.tsx render fns). Unwrap exactly as the story does. Falls back to the whole payload if
// it's already the inner data object (defensive).
function unwrapData<T>(payload: any): T {
  if (payload && typeof payload === "object" && payload.data && typeof payload.data === "object") {
    return payload.data as T;
  }
  return payload as T;
}

// ── cards ────────────────────────────────────────────────────────────────────
// Each card receives the host's `onDateChange` — calling it re-fetches JUST this card's ems_backend frame for the new
// window and re-renders the card. Both cards here carry a period control, so each forwards its picked period (mapped to
// the ems_backend window) into onDateChange. `onDateChange` is optional-called (older host call paths omit it).
export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: (dw: { range?: string; sampling?: string; start?: string; end?: string }) => void) => React.ReactNode
> = {
  // 39 — Today's Energy (top-left). LIVE energy-power scalars → view-model `.todaysEnergy`.
  // Date control: TodaysEnergyCard header FilterPillSelect → onPeriodChange(period: string). Map period→window.
  39: (payload, frame, onDateChange) => {
    const seed = unwrapData<TodaysEnergyData>(payload);
    let data: TodaysEnergyData = seed;
    try {
      const vm = buildViewModel(frame);
      if (vm?.todaysEnergy) data = vm.todaysEnergy;
    } catch { /* honest-degrade to seed default */ }
    // guard: TodaysEnergyCard maps data.periodOptions (elided-seed fallback drops the array → .map() crash)
    if (!data || !Array.isArray(data.periodOptions)) return null;
    return (
      <TodaysEnergyCard
        data={data}
        onPeriodChange={(period: string) => onDateChange?.(periodToDateWindow(period))}
      />
    );
  },

  // 42 — Load Anomalies (bottom-right). HISTORY buckets/KPIs → view-model `.loadAnomalies`.
  // Date control: LoadAnomaliesChart header PeriodSelect → onPeriodChange(period: string). Map period→window.
  42: (payload, frame, onDateChange) => {
    const seed = unwrapData<LoadAnomaliesData>(payload);
    let data: LoadAnomaliesData = seed;
    try {
      const vm = buildViewModel(frame);
      if (vm?.loadAnomalies) data = vm.loadAnomalies;
    } catch { /* honest-degrade to seed default */ }
    // guard: LoadAnomaliesChart maps/indexes data.actualLoad (.length/.forEach/.map), .expectedLoad, .expectedRange
    // and .anomalies; the elided-seed fallback drops these arrays → "reading 'length'/'map'" crash.
    if (
      !data ||
      !Array.isArray(data.actualLoad) ||
      !Array.isArray(data.expectedLoad) ||
      !Array.isArray(data.expectedRange) ||
      !Array.isArray(data.anomalies)
    ) return null;
    return (
      <LoadAnomaliesChart
        data={data}
        onPeriodChange={(period: string) => onDateChange?.(periodToDateWindow(period))}
      />
    );
  },
};
