import React, { useState } from "react";
// COMPOSE cards: the few cards that are NOT one component but a component stacking sub-pieces (what the EMS page
// Layout does). Keyed by card_id; checked BEFORE the generic COMPONENTS map. Each returns the rendered node.
import { RealTimeHeatmapSection } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeHeatmapSection";
import { buildHeatmapSections } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/heatmapMetrics";
import { LiveScrubberBar } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/LiveScrubberBar";
import { RealTimeMonitoringFooter } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringFooter";
import { HEATMAP_PLAYBACK_LABELS } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/realTimeMonitoringConfig";
import { CardHeader } from "@cmd-v2/components/charts/primitives";
import { HeatmapSections } from "./rtm/HeatmapSections";   // the ONE RTM heatmap body (F16, 2026-07-12)

const labelsFromTabs = (tabs: any[]) => Object.fromEntries((tabs ?? []).map((t) => [t.key, t.label]));
const columnsFromTabs = (tabs: any[]) => (tabs ?? []).filter((t) => t.key !== "all").map((t) => t.key);


/** Card 6 — Live Scrubber / Step Control: the CMD_V2 LiveScrubberBar (the RTM footer's playback atom), fed straight
 *  from its own payload's chrome props ({liveMode, currentLabel, canStepBack, canStepForward} — the contract shape).
 *  Pure interaction chrome (card_handling nav_index / static_chrome): NO data leaves; the toggle word pair comes from
 *  payload.playback else CMD_V2's own single-source HEATMAP_PLAYBACK_LABELS (never a re-typed literal). Local state
 *  owns the live/frozen toggle (LiveScrubberBar is pure-render — parent owns liveMode). */
function ScrubberCard({ p }: { p: any }) {
  const [liveMode, setLiveMode] = useState<boolean>(p.liveMode !== false);
  const playback = p.playback ?? HEATMAP_PLAYBACK_LABELS;
  return (
    <div className="flex h-full min-h-0 w-full items-center px-4 py-2">
      <LiveScrubberBar
        liveMode={liveMode}
        currentLabel={String(p.currentLabel ?? "")}
        canStepBack={!!p.canStepBack}
        canStepForward={!!p.canStepForward}
        stopLabel={playback.stop}
        resumeLabel={playback.resume}
        onStepBack={() => {}}
        onStepForward={() => {}}
        onTogglePlay={() => setLiveMode((v) => !v)}
      />
    </div>
  );
}

/** Card 160 — Heatmap Footer (time-tick axis + scrubber + shade legend): the REAL CMD_V2 RealTimeMonitoringFooter,
 *  fed from its own payload ({metric, history, selectedSampleIndex, liveMode, currentLabel, canStepBack,
 *  canStepForward} — the contract shape). In the RTM composite it mounts borderless at the bottom of the heatmap
 *  Card, exactly where CMD_V2's Layout puts it. Interaction chrome: local state owns the cursor + live toggle
 *  (stepping freezes, resuming snaps the cursor back to Now — the Layout's semantics); optional chrome props
 *  (metricTabs/statusLegend/…) pass through when the payload carries them, else the component's own single-source
 *  defaults. Honest: an empty history renders an empty axis + the static legend — never fabricated ticks. */
function FooterCard({ p }: { p: any }) {
  const history: any[] = Array.isArray(p.history) ? p.history : [];
  const last = Math.max(0, history.length - 1);
  const initIdx = typeof p.selectedSampleIndex === "number"
    ? Math.min(Math.max(0, p.selectedSampleIndex), last) : last;
  const [idx, setIdx] = useState<number>(initIdx);
  const [liveMode, setLiveMode] = useState<boolean>(p.liveMode !== false);
  const currentLabel = history[idx]?.label ?? p.currentLabel ?? "";
  return (
    <RealTimeMonitoringFooter
      metric={(p.metric ?? "all") as any}
      history={history as any}
      selectedSampleIndex={idx}
      liveMode={liveMode}
      currentLabel={String(currentLabel)}
      canStepBack={history.length > 0 ? idx > 0 : !!p.canStepBack}
      canStepForward={history.length > 0 ? idx < last : !!p.canStepForward}
      metricTabs={p.metricTabs ?? undefined}
      metricAxisLabels={p.metricAxisLabels ?? undefined}
      statusColors={p.statusColors ?? undefined}
      statusLegend={p.statusLegend ?? undefined}
      nowLabel={p.nowLabel ?? undefined}
      playback={p.playback ?? undefined}
      onStepBack={() => { setIdx((i) => Math.max(0, i - 1)); setLiveMode(false); }}
      onStepForward={() => { setIdx((i) => Math.min(last, i + 1)); setLiveMode(false); }}
      onTogglePlay={() => setLiveMode((v) => { const nv = !v; if (nv) setIdx(last); return nv; })}
    />
  );
}

export const COMPOSE: Record<number, (payload: any) => React.ReactNode> = {
  5: (p) => (p?.heatmap ? <HeatmapSections heatmap={p.heatmap} bordered /> : null),   // the ONE heatmap body (F16)
  // 6/160 — the RTM heatmap's interaction chrome (CMD_V2 LiveScrubberBar / RealTimeMonitoringFooter), composed the
  // CMD_V2-faithful way from each card's OWN payload chrome props. Tolerant of a one-level wrap (unwrap-style).
  6: (p) => {
    const s = p && typeof p === "object" ? (p.scrubber ?? p.footer ?? p) : null;
    return s && typeof s === "object" ? <ScrubberCard p={s} /> : null;
  },
  160: (p) => {
    const f = p && typeof p === "object" ? (p.footer ?? p.heatmap ?? p) : null;
    return f && typeof f === "object" ? <FooterCard p={f} /> : null;
  },
};
