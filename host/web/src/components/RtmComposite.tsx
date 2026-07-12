import React, { useMemo, useState } from "react";
import type { Card as CardT } from "../types";
import { renderCmd } from "../cmd/registry";
import { HeatmapSections, unwrap } from "../cmd/rtm/HeatmapSections";   // the ONE RTM heatmap body + payload prober (F16)

// COMPOSITE renderer for the RTM (panel-overview / real-time-monitoring) flex page. The EMS page is NOT 8 floating
// boxes — it is TWO Cards (RealTimeMonitoringLayout): a LEFT heatmap Card { Overview header · heatmap sections ·
// footer · scrubber } and a RIGHT rail Card { header · AiSummary · SupplyCard · TrendCard · QuickStats }. Layer 2
// still emits all 8 cards individually (each with its own swap + payload); this is a PURE FRONTEND grouping
// that merges them into the 2 Cards, with every inner piece rendered BORDERLESS so it reads as one card.
//
// Each piece is fed from ITS OWN card's payload (8-card specific; the page-frame plumbing is retired — F14,
// 2026-07-12). We reuse CMD V2's own exports and mappers
// exactly as cmd/compose.tsx and the fill module do — the same recipe useRealTimeMonitoringData / the page Layout run.
//   - card 7  → Overview HEADER ONLY (title/subtitle/statusBadge), NOT the whole rail.
//   - card 5  → heatmap sections (borderless; the COMPOSE HeatmapCard minus its outer Card+header).
//   - cards 160/6/8/9/10/11 → already render BARE borderless CMD V2 components via their FILL fns → reuse renderCmd.
//
// HONEST-DEGRADE: a missing payload for any piece renders that piece's placeholder/skip — never crashes the
// whole composite (each piece is wrapped in PieceBoundary).

// --- CMD V2 primitives / sections (read-only, via the @cmd-v2 vite alias; same imports compose.tsx / fill use) ---
import { Card as DSCard, CardHeader, TEXT, TYPOGRAPHY } from "@cmd-v2/components/charts/primitives";
import { RealTimeHeatmapSection } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeHeatmapSection";
import { RailStatusPill } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRailCards";
import { buildHeatmapSections } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/heatmapMetrics";
import { SegmentedControl } from "@cmd-v2/components/charts/primitives";

// Per-piece error boundary: one piece's render error degrades to a small note, never tears down the composite.
import { ErrorBoundary } from "./ErrorBoundary";
const Piece = ({ children }: { children: React.ReactNode }) => (
  <ErrorBoundary fallback={() => <div className="px-4 py-2 text-[11px]" style={{ color: TEXT.muted }}>piece unavailable</div>}>
    {children}
  </ErrorBoundary>
);

const byId = (cards: CardT[]) => {
  const m: Record<number, CardT> = {};
  for (const c of cards) m[c.render_card_id ?? c.card_id] = c;
  return m;
};
// "Open the box": the seed payload wraps the real prop one level down under `key` (e.g. { railVM } / { heatmap }).

/** Card 7 — Overview HEADER ONLY. The real RailHeader (CardHeader title = name+subtitle, action = status pill),
 *  but rendered borderless at the top of the LEFT composite — from the card's OWN payload railVM; honest-degrade
 *  to a neutral title when absent. */
function OverviewHeader({ card }: { card?: CardT }) {
  const vm = unwrap(card?.payload, "railVM");
  const title: string = (vm && typeof vm.title === "string" && vm.title) || "Overview";
  const subtitle: string | undefined = vm?.subtitle;
  const badge = vm?.statusBadge;
  const composedTitle = (
    <div className="flex min-w-0 flex-col">
      <span className="truncate" style={TYPOGRAPHY.cardTitle}>{title}</span>
      {subtitle && (
        <span className="mt-0.5 text-[10px] truncate" style={{ color: TEXT.muted }}>{subtitle}</span>
      )}
    </div>
  );
  return (
    <div className="px-4 pt-3 pb-1">
      <CardHeader title={composedTitle} action={badge ? <RailStatusPill badge={badge} /> : undefined} />
    </div>
  );
}

/** Card 5 — heatmap title + metric tabs + SECTIONS, borderless — the ONE shared body (cmd/rtm/HeatmapSections,
 *  F16 2026-07-12); this thin wrapper only unwraps the card payload. */
function HeatmapBody({ card }: { card?: CardT }) {
  return <HeatmapSections heatmap={unwrap(card?.payload, "heatmap") ?? {}} />;
}

/** Render an already-borderless FILL card (160/6/8/9/10/11) via the shared registry, so a swapped-in card renders
 *  by its OWN identity. Returns null when the card is absent or its fill honest-degrades (no payload). */
function FillPiece({ card }: { card?: CardT }) {
  if (!card) return null;
  return <>{renderCmd(card)}</>;
}

// The footer/scrubber (160/6) is CHROME for the SAME history the heatmap shows — CMD_V2's Layout derives the footer
// state from ONE shared history. Layer 2 authors that chrome with empty labels (it cannot know runtime timestamps),
// so when the footer's OWN payload carries no real tick label, ride card 5's REAL heatmap.history (real member-row
// timestamps) — a same-page fact share, never a fabricated tick. No real history anywhere → the footer's own empty
// state stands (honest).
const hasRealLabel = (h: any): boolean =>
  Array.isArray(h) && h.some((s: any) => typeof s?.label === "string" && s.label.trim() !== "");

function withHeatmapCursor(c160: CardT | undefined, c5: CardT | undefined): CardT | undefined {
  if (!c160) return c160;
  const own = (c160.payload as any)?.footer ?? (c160.payload as any)?.heatmap ?? c160.payload;
  const heatHistory = ((c5?.payload as any)?.heatmap ?? {})?.history;
  if (hasRealLabel(own?.history) || !hasRealLabel(heatHistory)) return c160;
  const last = heatHistory.length - 1;
  return {
    ...c160,
    payload: {
      ...(typeof own === "object" && own ? own : {}),
      history: heatHistory,
      selectedSampleIndex: last,
      currentLabel: heatHistory[last]?.label ?? "",
      canStepBack: last > 0,
      canStepForward: false,
      liveMode: own?.liveMode !== false,
    },
  } as CardT;
}

export function RtmComposite({ cards }: { cards: CardT[] }) {
  const m = byId(cards);
  const c7 = m[7], c5 = m[5], c160 = withHeatmapCursor(m[160], m[5]);
  const c8 = m[8], c9 = m[9], c10 = m[10], c11 = m[11];

  // NOTE: card 6 (Live Scrubber) is NOT rendered separately — RealTimeMonitoringFooter (card 160) ALREADY embeds the
  // LiveScrubberBar (CMD V2 RealTimeMonitoringFooter.tsx imports + renders it). The template split it into its own
  // atom, but in the real component the scrubber lives inside the footer; rendering both = a duplicate "Stop" control.

  return (
    <>
      {/* LEFT composite — ONE heatmap Card: overview header (7) · heatmap sections (5) · footer+scrubber (160) */}
      <div style={{ gridColumn: 1, minHeight: 0, overflow: "hidden" }}>
        <DSCard className="h-full" overflow="hidden" style={{ padding: 0, gap: 0 }}>
          <Piece><OverviewHeader card={c7} /></Piece>
          <Piece><HeatmapBody card={c5} /></Piece>
          <Piece><FillPiece card={c160} /></Piece>
        </DSCard>
      </div>

      {/* RIGHT composite — ONE rail Card: AiSummary (8) · SupplyCard (9) · TrendCard (10) · QuickStats (11) */}
      <div style={{ gridColumn: 2, minHeight: 0, overflow: "hidden" }}>
        <DSCard className="h-full" overflow="hidden" style={{ padding: 12, gap: 12 }}>
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto scroll-on-hover">
            <Piece><FillPiece card={c8} /></Piece>
            <Piece><FillPiece card={c9} /></Piece>
            <Piece><FillPiece card={c10} /></Piece>
            <Piece><FillPiece card={c11} /></Piece>
          </div>
        </DSCard>
      </div>
    </>
  );
}
