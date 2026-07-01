import React, { useState } from "react";
// COMPOSE cards: the few cards that are NOT one component but a component stacking sub-pieces (what the EMS page
// Layout does). Keyed by card_id; checked BEFORE the generic COMPONENTS map. Each returns the rendered node.
import { RealTimeHeatmapSection } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/RealTimeHeatmapSection";
import { buildHeatmapSections } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/heatmapMetrics";
import { mapFrame } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/realtime-monitoring/realTimeMonitoringMapper";
import { Card, CardHeader, SegmentedControl } from "@cmd-v2/components/charts/primitives";

const labelsFromTabs = (tabs: any[]) => Object.fromEntries((tabs ?? []).map((t) => [t.key, t.label]));
const columnsFromTabs = (tabs: any[]) => (tabs ?? []).filter((t) => t.key !== "all").map((t) => t.key);

/** Card 5 — RTM heatmap: composed from CMD_V2's own reusable exports (the page Layout's recipe), fed our payload.
 *  Live: map the ems_backend frame to history via CMD_V2's own mapper; else the default history. */
function HeatmapCard({ heatmap, liveFrame }: { heatmap: any; liveFrame?: any }) {
  const [metric, setMetric] = useState<string>(heatmap.metric ?? "all");
  let history = heatmap.history ?? [];
  try { if (liveFrame) { const snap: any = mapFrame(liveFrame); if (snap?.history?.length) history = snap.history; } } catch { /* keep default */ }
  const sections = buildHeatmapSections(history, heatmap.selectedSectionId);
  const metricLabels = labelsFromTabs(heatmap.metricTabs);
  const metricColumns = columnsFromTabs(heatmap.metricTabs);
  const sampleIdx = Math.max(0, (history.length || 1) - 1);
  return (
    <Card className="flex-1" overflow="hidden" style={{ padding: 0, gap: 0 }}>
      <div className="px-4 pt-3 pb-1">
        <CardHeader title={heatmap.title}
          action={<SegmentedControl value={metric} onChange={(v: string) => setMetric(v)} size="sm"
            options={(heatmap.metricTabs ?? []).map((t: any) => ({ value: t.key, label: t.label }))} />} />
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-4 py-2">
        {sections.map(({ sectionDef, buckets, selected }: any) => (
          <RealTimeHeatmapSection key={sectionDef.id} buckets={buckets} selectedSampleIndex={sampleIdx}
            metric={metric as any} sectionContracts={heatmap.sectionContracts} selected={selected}
            units={heatmap.units} descriptors={heatmap.descriptors} selectionColors={heatmap.selectionColors}
            statusColors={heatmap.statusColors} metricLabels={metricLabels} metricColumns={metricColumns as any}
            bandThresholds={heatmap.bandThresholds} onSectionToggle={() => {}} onCellSelect={() => {}} />
        ))}
      </div>
    </Card>
  );
}

export const COMPOSE: Record<number, (payload: any, liveFrame?: any) => React.ReactNode> = {
  5: (p, lf) => (p?.heatmap ? <HeatmapCard heatmap={p.heatmap} liveFrame={lf} /> : null),
};
