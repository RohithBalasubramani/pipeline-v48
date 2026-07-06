import React, { useMemo, useState } from "react";
import type { Card as CardT } from "../types";
import { renderCmd } from "../cmd/registry";

// COMPOSITE renderer for the RTM (panel-overview / real-time-monitoring) flex page. The EMS page is NOT 8 floating
// boxes — it is TWO Cards (RealTimeMonitoringLayout): a LEFT heatmap Card { Overview header · heatmap sections ·
// footer · scrubber } and a RIGHT rail Card { header · AiSummary · SupplyCard · TrendCard · QuickStats }. Layer 2
// still emits all 8 cards individually (each with its own swap + payload + frame); this is a PURE FRONTEND grouping
// that merges them into the 2 Cards, with every inner piece rendered BORDERLESS so it reads as one card.
//
// Each piece is fed from ITS OWN card's payload + frame (8-card specific). We reuse CMD V2's own exports and mappers
// exactly as cmd/compose.tsx and the fill module do — the same recipe useRealTimeMonitoringData / the page Layout run.
//   - card 7  → Overview HEADER ONLY (title/subtitle/statusBadge), NOT the whole rail.
//   - card 5  → heatmap sections (borderless; the COMPOSE HeatmapCard minus its outer Card+header).
//   - cards 160/6/8/9/10/11 → already render BARE borderless CMD V2 components via their FILL fns → reuse renderCmd.
//
// HONEST-DEGRADE: a missing payload/frame for any piece renders that piece's placeholder/skip — never crashes the
// whole composite (each piece is wrapped in PieceBoundary).

// --- CMD V2 primitives / sections (read-only, via the @cmd-v2 vite alias; same imports compose.tsx / fill use) ---
import { Card as DSCard, CardHeader, TEXT, TYPOGRAPHY } from "@cmd-v2/components/charts/primitives";
import { RealTimeHeatmapSection } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeHeatmapSection";
import { RailStatusPill } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRailCards";
import { buildHeatmapSections } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/heatmapMetrics";
import { mapFrame } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/realTimeMonitoringMapper";
import { buildRailViewModel } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/realTimeRailViewModel";
import { SegmentedControl } from "@cmd-v2/components/charts/primitives";

const PANEL_SELECTION: any = { kind: "panel" };

// Per-piece error boundary: one piece's render error degrades to a small note, never tears down the composite.
class PieceBoundary extends React.Component<{ children: React.ReactNode }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: any) { return { err: String(e?.message ?? e) }; }
  render() {
    if (this.state.err)
      return <div className="px-4 py-2 text-[11px]" style={{ color: TEXT.muted }}>piece unavailable</div>;
    return this.props.children;
  }
}
const Piece = ({ children }: { children: React.ReactNode }) => <PieceBoundary>{children}</PieceBoundary>;

const byId = (cards: CardT[]) => {
  const m: Record<number, CardT> = {};
  for (const c of cards) m[c.render_card_id ?? c.card_id] = c;
  return m;
};
const frameFor = (c: CardT | undefined, frames?: Record<string, any>): any =>
  (c?.endpoint && frames && frames[c.endpoint]) || undefined;

// "Open the box": the seed payload wraps the real prop one level down under `key` (e.g. { railVM } / { heatmap }).
function unwrap(payload: any, key: string): any {
  if (payload && typeof payload === "object" && payload[key] != null) return payload[key];
  return payload;
}

// Live RailViewModel from THIS page's aggregate frame — the SAME chain the fill module + the page hook run.
// Returns undefined on no frame / no mappable history so the caller keeps the seed payload (honest-degrade).
function liveRailVM(frame: any): any | undefined {
  if (!frame) return undefined;
  try {
    const snap: any = mapFrame(frame);
    const history = snap?.history;
    if (!Array.isArray(history) || history.length === 0) return undefined;
    const cursor = history[history.length - 1];
    return buildRailViewModel(PANEL_SELECTION, cursor, history, snap?.config?.sectionContracts);
  } catch {
    return undefined;
  }
}

/** Card 7 — Overview HEADER ONLY. The real RailHeader (CardHeader title = name+subtitle, action = status pill),
 *  but rendered borderless at the top of the LEFT composite. Live frame overrides the seed railVM; honest-degrade
 *  to a neutral title when neither is present. */
function OverviewHeader({ card, frame }: { card?: CardT; frame?: any }) {
  const seed = unwrap(card?.payload, "railVM");
  const vm = liveRailVM(frame) ?? seed;
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

/** Card 5 — heatmap title + metric tabs + SECTIONS, borderless (the COMPOSE HeatmapCard minus its outer Card).
 *  Live frame → CMD V2's own mapFrame → history; else the seed heatmap.history. Same recipe as cmd/compose.tsx. */
function HeatmapBody({ card, frame }: { card?: CardT; frame?: any }) {
  const heatmap = unwrap(card?.payload, "heatmap") ?? {};
  const [metric, setMetric] = useState<string>(heatmap.metric ?? "all");
  const history = useMemo(() => {
    let h = heatmap.history ?? [];
    try { if (frame) { const snap: any = mapFrame(frame); if (snap?.history?.length) h = snap.history; } } catch { /* keep seed */ }
    return h;
  }, [heatmap, frame]);
  const sections = useMemo(() => buildHeatmapSections(history, heatmap.selectedSectionId), [history, heatmap.selectedSectionId]);
  const metricLabels = useMemo(
    () => Object.fromEntries((heatmap.metricTabs ?? []).map((t: any) => [t.key, t.label])),
    [heatmap.metricTabs],
  );
  const metricColumns = useMemo(
    () => (heatmap.metricTabs ?? []).filter((t: any) => t.key !== "all").map((t: any) => t.key),
    [heatmap.metricTabs],
  );
  const sampleIdx = Math.max(0, (history.length || 1) - 1);

  if (history.length === 0)
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-6 text-[13px]" style={{ color: TEXT.muted }}>
        Connecting to live data…
      </div>
    );

  return (
    <>
      <div className="px-4 pt-2 pb-1">
        <CardHeader
          title={heatmap.title ?? "Real Time Monitoring"}
          action={
            <SegmentedControl
              value={metric}
              onChange={(v: string) => setMetric(v)}
              size="sm"
              options={(heatmap.metricTabs ?? []).map((t: any) => ({ value: t.key, label: t.label }))}
            />
          }
        />
      </div>
      <div className="scroll-on-hover flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overflow-x-hidden px-4 py-2">
        {sections.map(({ sectionDef, buckets, selected }: any) => (
          <RealTimeHeatmapSection
            key={sectionDef.id}
            buckets={buckets}
            selectedSampleIndex={sampleIdx}
            metric={metric as any}
            sectionContracts={heatmap.sectionContracts}
            selected={selected}
            units={heatmap.units}
            descriptors={heatmap.descriptors}
            selectionColors={heatmap.selectionColors}
            statusColors={heatmap.statusColors}
            metricLabels={metricLabels}
            metricColumns={metricColumns as any}
            bandThresholds={heatmap.bandThresholds}
            onSectionToggle={() => {}}
            onCellSelect={() => {}}
          />
        ))}
      </div>
    </>
  );
}

/** Render an already-borderless FILL card (160/6/8/9/10/11) via the shared registry, so a swapped-in card renders
 *  by its OWN identity. Returns null when the card is absent or its fill honest-degrades (no payload/frame). */
function FillPiece({ card, frame }: { card?: CardT; frame?: any }) {
  if (!card) return null;
  return <>{renderCmd(card, frame)}</>;
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

export function RtmComposite({ cards, frames }: { cards: CardT[]; frames?: Record<string, any> }) {
  const m = byId(cards);
  const c7 = m[7], c5 = m[5], c160 = withHeatmapCursor(m[160], m[5]);
  const c8 = m[8], c9 = m[9], c10 = m[10], c11 = m[11];

  // The RTM composite is ONE page sharing ONE live frame (the real-time-monitoring endpoint). Non-data atoms — the
  // footer (160) and header (7) — carry NO endpoint of their own, so frameFor() returns undefined for them; the footer
  // has no seed payload either, so without the frame it honest-degrades to NOTHING (the missing footer). Resolve the
  // shared frame from whichever piece DOES carry the endpoint, and every piece falls back to it.
  const rtm =
    frameFor(c5, frames) ?? frameFor(c160, frames) ?? frameFor(c7, frames) ??
    frameFor(c8, frames) ?? frameFor(c9, frames) ?? frameFor(c10, frames) ?? frameFor(c11, frames);

  // NOTE: card 6 (Live Scrubber) is NOT rendered separately — RealTimeMonitoringFooter (card 160) ALREADY embeds the
  // LiveScrubberBar (CMD V2 RealTimeMonitoringFooter.tsx imports + renders it). The template split it into its own
  // atom, but in the real component the scrubber lives inside the footer; rendering both = a duplicate "Stop" control.

  return (
    <>
      {/* LEFT composite — ONE heatmap Card: overview header (7) · heatmap sections (5) · footer+scrubber (160) */}
      <div style={{ gridColumn: 1, minHeight: 0, overflow: "hidden" }}>
        <DSCard className="h-full" overflow="hidden" style={{ padding: 0, gap: 0 }}>
          <Piece><OverviewHeader card={c7} frame={frameFor(c7, frames) ?? rtm} /></Piece>
          <Piece><HeatmapBody card={c5} frame={frameFor(c5, frames) ?? rtm} /></Piece>
          <Piece><FillPiece card={c160} frame={frameFor(c160, frames) ?? rtm} /></Piece>
        </DSCard>
      </div>

      {/* RIGHT composite — ONE rail Card: AiSummary (8) · SupplyCard (9) · TrendCard (10) · QuickStats (11) */}
      <div style={{ gridColumn: 2, minHeight: 0, overflow: "hidden" }}>
        <DSCard className="h-full" overflow="hidden" style={{ padding: 12, gap: 12 }}>
          <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto scroll-on-hover">
            <Piece><FillPiece card={c8} frame={frameFor(c8, frames) ?? rtm} /></Piece>
            <Piece><FillPiece card={c9} frame={frameFor(c9, frames) ?? rtm} /></Piece>
            <Piece><FillPiece card={c10} frame={frameFor(c10, frames) ?? rtm} /></Piece>
            <Piece><FillPiece card={c11} frame={frameFor(c11, frames) ?? rtm} /></Piece>
          </div>
        </DSCard>
      </div>
    </>
  );
}
