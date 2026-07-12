// cmd/rtm/HeatmapSections.tsx — the ONE RTM heatmap body (frontend F16, 2026-07-12). The same header
// (CardHeader + SegmentedControl over heatmap.metricTabs) + section list (buildHeatmapSections →
// <RealTimeHeatmapSection> 12-prop pass-through) was implemented twice: compose.tsx HeatmapCard (bordered — card 5
// swapped onto a grid page) and RtmComposite HeatmapBody (borderless — the RTM flex page). Variant differences are
// PRESERVED verbatim behind `bordered`: the borderless body keeps its "Connecting to live data…" empty state,
// default title, scroll-on-hover chrome and tighter header padding; the bordered card keeps its <Card> wrapper and
// no empty state. Metric-tab state stays LOCAL per instance. `unwrap` (the payload key prober) lives here too so
// both consumers share one definition.
import React, { useMemo, useState } from "react";
import { RealTimeHeatmapSection } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeHeatmapSection";
import { buildHeatmapSections } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/heatmapMetrics";
import { Card, CardHeader, SegmentedControl, TEXT } from "@cmd-v2/components/charts/primitives";

/** The payload key prober both RTM consumers use: payload[key] when present, else the payload itself. */
export function unwrap(payload: any, key: string): any {
  if (payload && typeof payload === "object" && payload[key] != null) return payload[key];
  return payload;
}

export function HeatmapSections({ heatmap, bordered }: { heatmap: any; bordered?: boolean }) {
  const [metric, setMetric] = useState<string>(heatmap.metric ?? "all");
  const history = useMemo(() => heatmap.history ?? [], [heatmap]);
  const sections = useMemo(() => buildHeatmapSections(history, heatmap.selectedSectionId),
    [history, heatmap.selectedSectionId]);
  const metricLabels = useMemo(
    () => Object.fromEntries((heatmap.metricTabs ?? []).map((t: any) => [t.key, t.label])),
    [heatmap.metricTabs],
  );
  const metricColumns = useMemo(
    () => (heatmap.metricTabs ?? []).filter((t: any) => t.key !== "all").map((t: any) => t.key),
    [heatmap.metricTabs],
  );
  const sampleIdx = Math.max(0, (history.length || 1) - 1);

  if (!bordered && history.length === 0)
    return (
      <div className="flex flex-1 items-center justify-center px-4 py-6 text-[13px]" style={{ color: TEXT.muted }}>
        Connecting to live data…
      </div>
    );

  const body = (
    <>
      <div className={bordered ? "px-4 pt-3 pb-1" : "px-4 pt-2 pb-1"}>
        <CardHeader
          title={bordered ? heatmap.title : (heatmap.title ?? "Real Time Monitoring")}
          action={
            <SegmentedControl value={metric} onChange={(v: string) => setMetric(v)} size="sm"
              options={(heatmap.metricTabs ?? []).map((t: any) => ({ value: t.key, label: t.label }))} />
          }
        />
      </div>
      <div className={bordered
        ? "flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-4 py-2"
        : "scroll-on-hover flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overflow-x-hidden px-4 py-2"}>
        {sections.map(({ sectionDef, buckets, selected }: any) => (
          <RealTimeHeatmapSection key={sectionDef.id} buckets={buckets} selectedSampleIndex={sampleIdx}
            metric={metric as any} sectionContracts={heatmap.sectionContracts} selected={selected}
            units={heatmap.units} descriptors={heatmap.descriptors} selectionColors={heatmap.selectionColors}
            statusColors={heatmap.statusColors} metricLabels={metricLabels} metricColumns={metricColumns as any}
            bandThresholds={heatmap.bandThresholds} onSectionToggle={() => {}} onCellSelect={() => {}} />
        ))}
      </div>
    </>
  );
  return bordered
    ? <Card className="flex-1" overflow="hidden" style={{ padding: 0, gap: 0 }}>{body}</Card>
    : body;
}
