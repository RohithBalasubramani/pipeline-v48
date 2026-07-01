import React from "react";
// FILL module — page: panel-overview-shell/real-time-monitoring.
// Wires each card on this page to its REAL CMD V2 component WITH live ems_backend data, via the card's OWN
// CMD V2 mapper + view-model builder (NEVER a re-implemented transform). Honest-degrade: every live mapping is
// wrapped in try/catch so a missing/unmappable frame falls back to the card's default (seed) payload.
//
// LIVE DATA PATH (cards 7/9/10/11 — the right rail):
//   ems_backend aggregate frame --mapFrame--> RealTimeMonitoringSnapshot (history + config.sectionContracts)
//   --> cursor = latest sample, selection = { kind: 'panel' } (page default, no feeder/section picked)
//   --buildRailViewModel--> RailViewModel ; card 7 = whole VM, 9 = .supply, 10 = .trend, 11 = .quickStats.
// This is exactly the chain useRealTimeMonitoringData runs (history -> railVM), reusing the SAME exported pure fns.
//
// Card 5 (RTM heatmap) is the COMPOSE reference (cmd/compose.tsx) and stays there — NOT re-registered here.
// Card 37 (VoltageMonitorPanel) is a cross-shell equipment-detail card whose mapper consumes a per-MFM COLUMN-ROW
//   socket (mapRealTimeMonitoringSocketToSnapshot), which is incompatible with THIS page's aggregate frame —
//   so it honest-degrades to its seed payload (no live mapping possible from the page-overview frame).

import { mapFrame } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/realTimeMonitoringMapper";
import { buildRailViewModel } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/realTimeRailViewModel";
import { buildHeatmapViewModel } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/heatmapMetrics";
import {
  RealTimeMonitoringRail,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRail";
import {
  SupplyCard,
  TrendCard,
  QuickStats,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringRailCards";
import { RealTimeMonitoringFooter } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringFooter";
import { LiveScrubberBar } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/LiveScrubberBar";
import type {
  HeatmapViewModel,
  HistorySample,
  RailViewModel,
  RailSelection,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/types";

import { AiSummary } from "@cmd-v2/components/charts/primitives";

import { VoltageMonitorPanel } from "@cmd-v2/pages/electrical/tabs/real-time-monitoring/VoltageMonitorPanel";

const PANEL_SELECTION: RailSelection = { kind: "panel" };

/** Map THIS page's live ems_backend frame to a fresh RailViewModel via CMD V2's own pure fns.
 *  Returns undefined when there is no frame or no mappable history → caller keeps the seed payload. */
function liveRailVM(frame: any): RailViewModel | undefined {
  if (!frame) return undefined;
  try {
    const snap: any = mapFrame(frame);
    const history = snap?.history;
    if (!Array.isArray(history) || history.length === 0) return undefined;
    const cursor = history[history.length - 1];
    const sectionContracts = snap?.config?.sectionContracts;
    return buildRailViewModel(PANEL_SELECTION, cursor, history, sectionContracts);
  } catch {
    return undefined;
  }
}

/** Open the box: the seed payload (story args) wraps the real prop one level down under `key` (+ a throwaway
 *  `variant`). Accept either the wrapped form ({ [key]: inner }) or an already-unwrapped inner. */
function unwrap(payload: any, key: string): any {
  if (payload && typeof payload === "object" && payload[key] != null) return payload[key];
  return payload;
}

/** The footer / scrubber / AI-summary cards (160 / 6 / 8) carry NO payload — everything is derived from the
 *  live ems_backend frame the SAME way `useRealTimeMonitoringData` derives it for the page Layout. This mirrors
 *  the hook's LIVE-mode defaults: liveMode = true → cursor parks on the latest bucket, no feeder/section picked.
 *
 *  Returns undefined when there is no frame or no mappable history → each card render returns null so the host
 *  shows its own placeholder (honest-degrade — never throws). */
interface LiveFooterState {
  history: HistorySample[];
  heatmap: HeatmapViewModel;
  effectiveSampleIndex: number;
  cursorLabel: string;
  liveMode: boolean;
  canStepBack: boolean;
  canStepForward: boolean;
}

function liveFooterState(frame: any): LiveFooterState | undefined {
  if (!frame) return undefined;
  try {
    const snap: any = mapFrame(frame);
    const history: HistorySample[] = snap?.history;
    if (!Array.isArray(history) || history.length === 0) return undefined;

    // Page default interaction state (no Stop pressed yet): live mode, latest bucket is the cursor, nothing picked.
    const liveMode = true;
    const latestSampleIndex = Math.max(0, history.length - 1);
    const effectiveSampleIndex = latestSampleIndex; // liveMode → follow latest (hook: useRealTimeMonitoringData)
    const cursorSample = history[effectiveSampleIndex];

    // The WHOLE heatmap card as one VM — same call the hook makes, threading the live interaction-state defaults.
    const heatmap = buildHeatmapViewModel(history, undefined, {
      metric: "all",
      selectedSampleIndex: effectiveSampleIndex,
      liveMode,
      selectedFeederId: undefined,
      backendSectionContracts: snap?.config?.sectionContracts,
    });

    return {
      history,
      heatmap,
      effectiveSampleIndex,
      cursorLabel: cursorSample?.label ?? "—",
      liveMode,
      canStepBack: effectiveSampleIndex > 0,
      canStepForward: effectiveSampleIndex < latestSampleIndex,
    };
  } catch {
    return undefined;
  }
}

/** Card 8's AI-summary text rides the RailViewModel (`railVM.aiSummaryText`) — the page derives it from the
 *  same panel-default rail the right rail uses. Returns undefined on any failure so the card honest-degrades. */
function liveAiSummaryText(frame: any): string | undefined {
  const vm = liveRailVM(frame);
  const text = vm?.aiSummaryText;
  return typeof text === "string" && text.length > 0 ? text : undefined;
}

const AI_SUMMARY_FALLBACK =
  "Live panel summary will appear once real-time feeder data is streaming.";

const noop = () => {};

export const CARDS: Record<number, (payload: any, frame?: any) => React.ReactNode> = {
  // Card 7 — full Overview Rail. Story args: { railVM }. Prop: railVM (the whole RailViewModel).
  7: (payload, frame) => {
    const seed = unwrap(payload, "railVM");
    const live = liveRailVM(frame);
    const railVM = live ?? seed;
    // guard: RealTimeMonitoringRail renders TrendCard (maps/spreads railVM.trend.series)
    // and QuickStats (maps railVM.quickStats) — both required data-leaf arrays the
    // elided seed drops → honest-degrade instead of crashing on `.map`/spread.
    if (!railVM || !Array.isArray(railVM.quickStats) || !Array.isArray(railVM.trend?.series)) return null;
    return <RealTimeMonitoringRail railVM={railVM} />;
  },

  // Card 9 — Total Feeder Consumption (SupplyCard). Story args: { supply }. Prop: supply (RailViewModel['supply']).
  9: (payload, frame) => {
    const seed = unwrap(payload, "supply");
    const live = liveRailVM(frame);
    return <SupplyCard supply={live?.supply ?? seed} />;
  },

  // Card 10 — Consumption Trend (TrendCard). Story args: { trend }. Prop: trend (RailViewModel['trend']).
  10: (payload, frame) => {
    const seed = unwrap(payload, "trend");
    const live = liveRailVM(frame);
    const trend = live?.trend ?? seed;
    // guard: TrendCard spreads/maps trend.series (Math.max(...series), series.map) —
    // required data-leaf array the elided seed drops → null instead of crashing.
    if (!trend || !Array.isArray(trend.series)) return null;
    return <TrendCard trend={trend} />;
  },

  // Card 11 — KPI Tiles (QuickStats). Story args: { stats, layout }. Props: stats, layout.
  11: (payload, frame) => {
    const seedStats = unwrap(payload, "stats");
    const seedLayout =
      payload && typeof payload === "object" && (payload.layout === "stack" || payload.layout === "grid")
        ? payload.layout
        : "grid";
    const live = liveRailVM(frame);
    const stats = live?.quickStats ?? seedStats;
    const layout = live?.quickStatsLayout ?? seedLayout;
    // guard: QuickStats maps `stats` — required data-leaf array the elided seed drops
    // → null instead of crashing on stats.map.
    if (!Array.isArray(stats)) return null;
    return <QuickStats stats={stats} layout={layout === "stack" ? "stack" : "grid"} />;
  },

  // Card 37 — Voltage Monitor Panel (cross-shell equipment-detail card). Story args: { data, freshness }.
  // Its mapper wants a per-MFM column-row socket, incompatible with this page's aggregate frame → seed only.
  37: (payload) => {
    const data = unwrap(payload, "data");
    const freshness =
      payload && typeof payload === "object" ? payload.freshness : undefined;
    // guard: VoltageMonitorPanel reads freshness.{label,tone,title} and PhaseMonitorPanel
    // maps data.legendItems + data.metrics (required data-leaf arrays the elided seed
    // drops) → null instead of crashing on `.map`.
    if (!data || !freshness || !Array.isArray(data.legendItems) || !Array.isArray(data.metrics)) return null;
    return <VoltageMonitorPanel data={data} freshness={freshness} />;
  },

  // Card 160 — Heatmap Footer (time-tick / All-Metrics axis row + the scrubber + the shade legend). NO payload —
  // every prop is derived from the live frame the SAME way the page Layout passes them: data (metric/history/
  // selectedSampleIndex/liveMode/currentLabel/canStep*) from the hook state + chrome (metricTabs/metricAxisLabels/
  // statusColors/statusLegend/nowLabel/playback) off the heatmap VM. Honest-degrade: no live state → null.
  160: (_payload, frame) => {
    const s = liveFooterState(frame);
    if (!s) return null;
    return (
      <RealTimeMonitoringFooter
        metric={s.heatmap.metric}
        history={s.history}
        selectedSampleIndex={s.effectiveSampleIndex}
        liveMode={s.liveMode}
        currentLabel={s.cursorLabel}
        canStepBack={s.canStepBack}
        canStepForward={s.canStepForward}
        metricTabs={s.heatmap.metricTabs}
        metricAxisLabels={s.heatmap.metricAxisLabels}
        statusColors={s.heatmap.statusColors}
        statusLegend={s.heatmap.statusLegend}
        nowLabel={s.heatmap.nowLabel}
        playback={s.heatmap.playback}
        onStepBack={noop}
        onStepForward={noop}
        onTogglePlay={noop}
      />
    );
  },

  // Card 6 — Live Scrubber / Step Control. NO payload — the same standalone scrubber the Footer embeds, fed the
  // live cursor state + the playback words off the heatmap VM. Cursor control is the deferred interdependency, so
  // the interactive callbacks are no-ops (render only). Honest-degrade: no live state → null.
  6: (_payload, frame) => {
    const s = liveFooterState(frame);
    if (!s) return null;
    return (
      <LiveScrubberBar
        liveMode={s.liveMode}
        currentLabel={s.cursorLabel}
        canStepBack={s.canStepBack}
        canStepForward={s.canStepForward}
        stopLabel={s.heatmap.playback.stop}
        resumeLabel={s.heatmap.playback.resume}
        onStepBack={noop}
        onStepForward={noop}
        onTogglePlay={noop}
      />
    );
  },

  // Card 8 — AI Summary. NO payload — the panel-default RailViewModel's `aiSummaryText` (exactly what the right
  // rail renders), else a sensible default string. Never null: AiSummary always has text to show.
  8: (_payload, frame) => {
    const text = liveAiSummaryText(frame) ?? AI_SUMMARY_FALLBACK;
    return <AiSummary text={text} density="compact" />;
  },
};
