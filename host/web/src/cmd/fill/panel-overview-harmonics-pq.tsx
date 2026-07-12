/**
 * FILL module — page panel-overview-shell/harmonics-pq (cards 23-27).
 *
 * Thin BARREL. The registry loads this via `import.meta.glob("./fill/*.tsx")`
 * and reads `m.CARDS`, so this file must keep exporting `CARDS`. Each card's
 * render fn + the shared helpers (date-window / derive / noop) live atomised,
 * one concern per file, in the same-named folder next to this file.
 *
 * PAYLOAD-DIRECT (host-served RETIRED — the host emits frames={} EMPTY): the ONLY data
 * source is each card's Layer-2 completed `payload` (real neuract periods/stats + honest-blank).
 * The old LIVE aggregate-frame path (snapshot.ts's mapPanelHarmonicsPqAggregateToSnapshot +
 * the per-card snapshotFromFrame branch) AND the buildPQPeriods() fabrication fallback (which
 * synthesised iThd/vThd/harmonic waves from a mock fixture — a SEED LEAK) are dead code now and
 * were DELETED. A payload that elides its periods degrades to derive.ts's honest-empty builders
 * (emptyPeriod / emptyPeriodWithRow / emptyStats — zero counts, '—' chrome, ZERO fabrication),
 * so every card DRAWS honest '—' chrome, never a mock. Card 23's date control stays live
 * (onDateChange = a payload re-fetch, not a frame path).
 */
import type { DateWindow } from "./panel-overview-harmonics-pq/date-window";
import { renderTopStrip } from "./panel-overview-harmonics-pq/card-23";
import { renderTimeline } from "./panel-overview-harmonics-pq/card-24";
import { renderAiSummary } from "./panel-overview-harmonics-pq/card-25";
import { renderFeederTable } from "./panel-overview-harmonics-pq/card-26";
import { renderSignature } from "./panel-overview-harmonics-pq/card-27";

import type React from "react";

export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: (dw: DateWindow) => void) => React.ReactNode
> = {
  23: renderTopStrip, // has date control — wired to onDateChange
  24: renderTimeline, // no date control (timeline point-click = intra-window bucket nav)
  25: renderAiSummary, // no date control (snapshot of the selected period)
  26: renderFeederTable, // no date control (feeder-row selection only)
  27: renderSignature, // no date control (feeder-row selection only)
};
