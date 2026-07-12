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

// COMPARISON TITLE [sections]: a split card must READ as a comparison — inject the section tokens into the header
// ("Event Timeline · 1A vs 1B at Today"). toks are the real bus-section tokens (executor-stamped); no toks → the
// plain title, so a non-compare render is byte-identical.
const cmpTitle = (prefix: any, connector: any, label: any, toks: string[]) => {
  const secs = (toks ?? []).filter(Boolean);
  const mid = secs.length ? ` · ${secs.join(" vs ")}` : "";
  return `${prefix ?? ""}${mid}${connector ?? ""}${label ?? ""}`;
};

// SECTION LEGEND [sections]: a swatch+label row the section cards render themselves (ComparisonRadarChart ships no
// static legend, and the strip/table have none), so every section series is named on the card, not just on hover.
function SectionLegend({ items }: { items: Array<{ color: string; label: string }> }) {
  if (!items.length) return null;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1" style={{ fontSize: 11, opacity: 0.8 }}>
      {items.map((it, i) => (
        <span key={i} className="inline-flex items-center gap-1.5">
          <span style={{ width: 10, height: 10, background: it.color, borderRadius: 2, display: "inline-block" }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

export function EventTimelineSections({ pres, period, points, selectedLabel, selectedTileKey, onPeriodSelect,
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
    <BodyCard title={cmpTitle(pres?.titlePrefix, pres?.titleConnector, period?.label, pres?.sectionCompare)}>
      {availability === "loading" ? (
        <CardBodySkeleton />
      ) : (
        <div className="h-full min-h-0">
          <EventTimelineChart
            points={points ?? []}
            xLabel={(p: any) => p?.label}
            stackSeries={stackSeries}
            lineSeries={lineSeries}
            showLegend={pres?.showLegend !== false}
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

// ── SECTION RADAR — a payload-driven view over the CMD_V2 ComparisonRadarChart primitive. ─────────────────────────
// The executor stamps `<subtree>.sectionCompare` (the bus-section tokens) on a section-compare run; each member row
// carries its own `section` attr. Series = one polygon per section (+ 'Common' for bus-level members) over the SAME
// member spokes — an off-section member draws 0 A from that section (physically true, never fabricated). Labels and
// colors are AI-MORPHABLE via `pres.sections` ([{token,label,color}]) with a deterministic fallback palette; spoke
// labels reuse pres.spokeLabelReplacements; the header reuses titlePrefix/titleConnector/period.label. Without the
// stamp the ORIGINAL card renders byte-identically.
import { ComparisonRadarChart } from "@cmd-v2/components/charts/primitives";

const SECTION_PALETTE = ["#7a4e13", "#4A6FA5", "#9aa3ab"];

const applyRepl = (s: string, repl: any[]) =>
  (Array.isArray(repl) ? repl : []).reduce(
    (acc, r) => (r && typeof r.from === "string" ? acc.split(r.from).join(r.to ?? "") : acc),
    String(s ?? ""));

export function SectionRadar({ distribution }: { distribution: any }) {
  const pres = distribution?.pres ?? {};
  const period = distribution?.period ?? {};
  const toks: string[] = (distribution?.sectionCompare ?? []).map((t: any) => String(t).toUpperCase());
  const rows = (Array.isArray(period.panels) ? period.panels : [])
    .filter((r: any) => r && r.amps != null && r.role !== "incoming");
  const secOf = (r: any) => {
    const s = String(r?.section ?? "").toUpperCase();
    return toks.includes(s) ? s : null;
  };
  const spokes = rows.map((r: any) => applyRepl(r.panel ?? r.id, pres.spokeLabelReplacements));
  // series spec: AI-morphable pres.sections wins; deterministic fallback = one per token + Common when present
  const spec: Array<{ token: string | null; label: string; color: string }> =
    (Array.isArray(pres.sections) && pres.sections.length
      ? pres.sections.map((s: any, i: number) => ({
          token: s?.token != null ? String(s.token).toUpperCase() : null,
          label: String(s?.label ?? s?.token ?? `Series ${i + 1}`),
          color: String(s?.color ?? SECTION_PALETTE[i % SECTION_PALETTE.length]) }))
      : [
          ...toks.map((t, i) => ({ token: t, label: `Sec ${t.slice(-1)}`, color: SECTION_PALETTE[i % SECTION_PALETTE.length] })),
          ...(rows.some((r: any) => secOf(r) == null)
            ? [{ token: null, label: "Common", color: SECTION_PALETTE[2] }]
            : []),
        ]);
  const series = spec.map((s) => ({
    key: s.token ?? "common",
    name: s.label,
    color: s.color,
    values: rows.map((r: any) => (secOf(r) === s.token ? num(r.amps) : 0)),
  }));
  // only legend the sections that actually place a member (an empty section adds noise, not information)
  const legend = spec.filter((s) => series.find((x) => x.key === (s.token ?? "common"))?.values.some((v) => v > 0))
    .map((s) => ({ color: s.color, label: s.label }));
  return (
    <BodyCard title={cmpTitle(pres.titlePrefix, pres.titleConnector, period.label, toks)}>
      <div className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1"><ComparisonRadarChart spokes={spokes} series={series} /></div>
        <SectionLegend items={legend} />
      </div>
    </BodyCard>
  );
}
