// section-split.tsx — sections-aware wrapper for CLOSED-VOCABULARY timeline cards. [sections overlay]
//
// WHY: a bus-section compare ('pcc 1a vs pcc 1b') ships per-section series keys (sag_a/sag_b …) in the payload's OWN
// pres lists (executor roster_pres_sections stamps `pres.sectionSplit: true` when it synthesized them). CMD_V2's
// EventTimelineCard maps series through a CLOSED accessor record (stackValueFor knows exactly sag/swell/current/
// neutral) — a variant key there is `value: undefined` → the chart throws. CMD_V2 is READ-ONLY, so the HOST renders
// the SAME CMD_V2 chart primitive (EventTimelineChart + BodyCard — never a hand-drawn chart) with accessors built
// GENERICALLY from each pres entry's key; base-key semantics are honored (a vWorst_* line plots its absolute
// deviation, exactly like the original card). No marker → the ORIGINAL component renders byte-identically.
import React from "react";
import { EventTimelineChart } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/EventTimelineChart";
import { BodyCard, CardBodySkeleton, composeMetricHeader } from "@cmd-v2/components/charts/primitives";

const baseOf = (k: string) => k.replace(/_[a-z]$/, "");
const num = (v: unknown) => {
  const n = Number(v ?? 0);
  return Number.isFinite(n) ? n : 0;
};

function EventTimelineSections({ pres, period, points, selectedLabel, selectedTileKey, onPeriodSelect,
                                 availability = "ready" }: any) {
  const stackDim = (key: string) =>
    selectedTileKey == null || selectedTileKey === key || selectedTileKey === baseOf(key)
      ? 1 : (pres?.dimOpacity?.stack ?? 1);
  const lineDim = (tileKey: string) =>
    selectedTileKey == null || selectedTileKey === tileKey ? 1 : (pres?.dimOpacity?.line ?? 1);
  const stackSeries = (pres?.stackOrder ?? []).flatMap((key: string) => {
    const s = (pres?.stackSeries ?? []).find((e: any) => e?.key === key);
    return s ? [{ key: s.key, label: s.label, color: s.color,
                  value: (p: any) => num(p?.[s.key]), opacity: stackDim(s.key) }] : [];
  });
  const lineSeries = (pres?.lineOrder ?? []).flatMap((key: string) => {
    const s = (pres?.lineSeries ?? []).find((e: any) => e?.key === key);
    const abs = baseOf(key) === "vWorst";                          // worst-V plots its ABSOLUTE deviation (original card)
    return s ? [{ key: s.key, label: s.label, color: s.color,
                  value: (p: any) => (abs ? Math.abs(num(p?.[s.key])) : num(p?.[s.key])),
                  opacity: lineDim(s.tileKey) }] : [];
  });
  return (
    <BodyCard title={`${pres?.titlePrefix ?? ""}${pres?.titleConnector ?? ""}${period?.label ?? ""}`}>
      {availability === "loading" ? (
        <CardBodySkeleton />
      ) : (
        <div className="h-full min-h-0">
          <EventTimelineChart
            points={points ?? []}
            xLabel={(p: any) => p?.label}
            stackSeries={stackSeries}
            lineSeries={lineSeries}
            showLegend={pres?.showLegend}
            showHoverTooltip
            selectedLabel={selectedLabel}
            onPointClick={onPeriodSelect}
            leftAxisLabel={pres?.leftAxisLabel}
            rightAxisLabel={composeMetricHeader({
              label: pres?.rightAxis?.label, unit: pres?.rightAxis?.unit, unitStyle: pres?.rightAxis?.unitStyle })}
          />
        </div>
      )}
    </BodyCard>
  );
}

/** The ORIGINAL component unless the payload's pres carries the executor's `sectionSplit` marker. */
export function withSectionSplit(Orig: React.ComponentType<any>): React.ComponentType<any> {
  return function SectionSplitSwitch(props: any) {
    return props?.pres?.sectionSplit ? <EventTimelineSections {...props} /> : <Orig {...props} />;
  };
}
