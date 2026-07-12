// prim/rtm-chrome.tsx — RTM heatmap body + playback chrome (cards 5 / 6 / 160). [primitives-only port]
//
// DOCUMENTED EXCEPTION to the barrel-only import rule (PORT_CONTRACT.md rule 1): the RTM heatmap section, live
// scrubber and footer are payload-GENERIC interaction widgets (metric tabs / axis labels / status colors / playback
// words all ride the payload — F16) with no barrel equivalent yet; they are barrel-promotion candidates on the
// CMD_V2 side (CMD_V2 is read-only from here, so the promotion cannot happen in this repo). They are NOT closed
// per-card page wrappers — nothing here freezes semantics the payload can't rebind. Bodies moved verbatim from the
// retired COMPOSE tier (cmd/compose.tsx).
import React, { useState } from "react";
import { LiveScrubberBar } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/LiveScrubberBar";
import { RealTimeMonitoringFooter } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeMonitoringFooter";
import { HEATMAP_PLAYBACK_LABELS } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/realTimeMonitoringConfig";
import { HeatmapSections } from "../rtm/HeatmapSections";

/** Card 6 — playback chrome: pure interaction atom, no data leaves; toggle words from payload else CMD_V2's own
 *  single-source labels. Local state owns the live/frozen toggle (the bar is pure-render). */
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

/** Card 160 — heatmap footer (tick axis + scrubber + legend). Local state owns the cursor + live toggle; stepping
 *  freezes, resuming snaps to Now. An empty history renders an empty axis + static legend — never fabricated ticks. */
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

export const CARDS: Record<number, (p: any) => React.ReactNode> = {
  5: (p) => (p?.heatmap ? <HeatmapSections heatmap={p.heatmap} bordered /> : null),
  6: (p) => {
    const s = p && typeof p === "object" ? (p.scrubber ?? p.footer ?? p) : null;
    return s && typeof s === "object" ? <ScrubberCard p={s} /> : null;
  },
  160: (p) => {
    const f = p && typeof p === "object" ? (p.footer ?? p.heatmap ?? p) : null;
    return f && typeof f === "object" ? <FooterCard p={f} /> : null;
  },
};
