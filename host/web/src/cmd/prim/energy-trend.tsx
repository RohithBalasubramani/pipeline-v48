// prim/energy-trend.tsx — the chart-heavy Energy&Power cards (16 EnergyTrend, 17 DemandProfile, 40 PowerEnergyAnalysis)
// on PRIMITIVES ONLY. [primitives-only port] Sibling of energy.tsx (which owns the CARDS record); this file exports
// plain React components it mounts. No CARDS export here → prim/index.ts's glob skips it for the registry merge.
//
// Every chart body is composed from ChartFrame/GridAxis/StackedBars/LinePath/ReferenceLine and lives inside
// ResponsiveSvg — which only paints once its container is measured, so under react-dom/server (the SSR gate) the SVG
// never renders and the card's header + legend rail + KPI chrome is what the gate exercises. Series rosters are looked
// up from the payload BY KEY (fieldOf(point,row.id)); every scalar goes through fin()/fmtNum() so an honest-blank leaf
// is '—' or an empty bar, never NaN geometry, never a crash.
import React from "react";
import {
  AiSummary,
  buildDivergingSegments,
  Card,
  CardHeader,
  ChartFrame,
  CHART_COLORS,
  composeMetricHeader,
  composeValueUnit,
  ExpandableLegend,
  GridAxis,
  InteractiveLegendRow,
  KpiStatStrip,
  LinePath,
  presetRange,
  ReferenceLine,
  ResponsiveSvg,
  SamplingPicker,
  SegmentedControl,
  sparseTickIndexes,
  StackedBars,
  StatusBadge,
  useInteractiveLegend,
  type SamplingSelection,
  type StatusTone,
} from "@cmd-v2/components/charts/primitives";
import { fin, dash, fmtNum } from "./shared";
import { samplingToWindow, type DateWindow } from "./energy-date";

const MARGIN = { top: 12, right: 12, bottom: 24, left: 64 };
const arr = (v: any): any[] => (Array.isArray(v) ? v : []);
/** series/index-signature value off a point row, honest-blank-safe. */
const fieldOf = (p: any, id: string): number | null => fin(p?.[id]);
const toneOf = (t: any): StatusTone =>
  (["fail", "critical", "warning", "success", "info", "neutral"].includes(String(t)) ? t : "neutral") as StatusTone;

/** nice-step y ticks over [min,max]; empty when degenerate. */
function niceTicks(min: number, max: number, count = 5): number[] {
  const range = max - min;
  if (!(range > 0)) return [min];
  const rough = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((c) => c >= rough) ?? mag * 10;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

function axisProps(labelText?: string) {
  return {
    showHorizontalGrid: true,
    horizontalGridDasharray: "3 3",
    gridColor: CHART_COLORS.cream300,
    axisLineColor: CHART_COLORS.cream400,
    labelColor: CHART_COLORS.teal500,
    yAxisLabel: labelText,
    yAxisTitleOffset: 50,
  } as const;
}

// ── the SamplingPicker header control (shared by 16/17/40; wired to onDateChange) ─────────────────────────────────
function useSampling(seedPeriod: string | undefined) {
  return React.useState<SamplingSelection>(() => {
    const p = String(seedPeriod ?? "").toLowerCase();
    const preset = p.includes("yester") ? "yesterday"
      : p.includes("7") || p.includes("week") ? "last-7-days"
      : p.includes("month") ? "this-month" : "today";
    return { preset, range: presetRange(preset as any, new Date()) };
  });
}
function PickerAction({ sampling, setSampling, presets, resolutionOptions, shiftOptions, onDateChange }: {
  sampling: SamplingSelection; setSampling: (s: SamplingSelection) => void;
  presets?: any; resolutionOptions?: any; shiftOptions?: any; onDateChange?: (dw: DateWindow) => void;
}) {
  return (
    <SamplingPicker
      value={sampling}
      presets={presets}
      resolutionOptions={resolutionOptions}
      shiftOptions={shiftOptions}
      shiftWhenResolution="by-shift"
      showCalendar
      align="end"
      onChange={(next) => {
        setSampling(next);
        try { onDateChange && onDateChange(samplingToWindow(next)); } catch { /* window stays */ }
      }}
    />
  );
}

// ── Card 40 — Power Energy Analysis (stacked A/R bars + avg line, or demand bars) ─────────────────────────────────
function PowerAnalysisBody({ d, view, lineOpacity, width, height }: {
  d: any; view: "active-reactive" | "demand";
  lineOpacity: number; width: number; height: number;
}) {
  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerH = Math.max(0, height - MARGIN.top - MARGIN.bottom);
  const demand = view === "demand";
  const yMin = fin(demand ? d.demandYMin : d.yMin) ?? 0;
  const yMax = fin(demand ? d.demandYMax : d.yMax) ?? (yMin + 1);
  const yRange = yMax - yMin || 1;
  const yScale = (v: number) => innerH - ((v - yMin) / yRange) * innerH;
  const bars = demand ? arr(d.demandBars) : arr(d.bars);
  const xSpacing = bars.length > 0 ? innerW / bars.length : 0;
  const xCenter = (i: number) => xSpacing * (i + 0.5);
  const barW = Math.max(6, Math.min(16, xSpacing * 0.42));
  const bandColor = (band: string) =>
    arr(d.demandBandLegend).find((it: any) => it?.band === band)?.color ?? CHART_COLORS.cream300;

  const stacked = bars.map((b: any, i: number) => ({
    id: `b-${i}`,
    x: xCenter(i),
    segments: demand
      ? buildDivergingSegments(
          [{ id: b?.band, value: fin(b?.value) ?? 0, color: bandColor(b?.band), capRadius: 2 }],
          yScale, { plotTop: MARGIN.top, innerHeight: innerH })
      : buildDivergingSegments(
          [{ id: "active", value: fin(b?.active) ?? 0, color: d.activeColor ?? CHART_COLORS.teal500, zeroRadius: 4 },
           { id: "reactive", value: fin(b?.reactive) ?? 0, color: d.reactiveColor ?? CHART_COLORS.sky300, capRadius: 4 }],
          yScale, { plotTop: MARGIN.top, innerHeight: innerH }),
  }));
  const yTicks = niceTicks(yMin, yMax, 6).map((v) => ({ y: yScale(v), label: String(v) }));
  const xTicks = sparseTickIndexes(bars.length, Math.max(2, Math.floor(innerW / 44)))
    .map((i) => ({ x: xCenter(i), label: String(bars[i]?.time ?? "") }));
  const linePts = demand ? [] : arr(d.hourlyAverage).map((v: any, i: number) => ({ x: xCenter(i), y: Math.max(0, Math.min(innerH, yScale(fin(v) ?? 0))) }));
  const refs = [
    { value: fin(demand ? d.ratedKw : d.ratedKw), placement: demand ? d.demandRatedKwPlacement : d.ratedKwPlacement, label: d.ratedLabel },
    { value: fin(d.contractedKw), placement: demand ? d.demandContractedKwPlacement : d.contractedKwPlacement, label: d.contractedLabel },
  ].filter((r) => r.value != null && r.value > 0 && r.placement == null);

  return (
    <ChartFrame width={width} height={height} margin={MARGIN}>
      {(plot) => (
        <>
          <GridAxis plot={plot} xTicks={xTicks} yTicks={yTicks}
            {...axisProps(d.yAxisTitle ? composeMetricHeader(d.yAxisTitle) : undefined)} />
          {refs.map((r) => (
            <ReferenceLine key={r.label} plot={plot} y={yScale(r.value as number)} tone="reference"
              label={`${r.label}: ${composeValueUnit(String(r.value), d.refLineUnit, " ")}`}
              placement="above" labelBackground="transparent" />
          ))}
          <StackedBars plot={plot} bars={stacked} barWidth={barW} segmentRadius={demand ? 2 : 4} />
          {linePts.length > 0 && (
            <LinePath plot={plot} points={linePts} stroke={d.averageColor ?? CHART_COLORS.mustard500}
              strokeWidth={2} markerRadius={0} opacity={lineOpacity} />
          )}
        </>
      )}
    </ChartFrame>
  );
}

export function PowerEnergyAnalysis40({ payload, onDateChange }: { payload: any; onDateChange?: (dw: DateWindow) => void }) {
  const d = payload?.data ?? {};
  const [view, setView] = React.useState<"active-reactive" | "demand">(d.view === "demand" ? "demand" : "active-reactive");
  const [sampling, setSampling] = useSampling(d.period);
  const ar = useInteractiveLegend<string>(["active", "reactive", "line"]);
  const demand = useInteractiveLegend<string>(["low", "moderate", "high"]);
  return (
    <Card className="h-full gap-3">
      <CardHeader title={dash(d.title)} action={
        <div className="flex items-center gap-2">
          {d.staleBadge ? <StatusBadge label={String(d.staleBadge.label ?? "")} tone={toneOf(d.staleBadge.tone)} /> : null}
          <PickerAction sampling={sampling} setSampling={setSampling} onDateChange={onDateChange} />
        </div>
      } />
      <div className="grid grid-cols-[minmax(0,1fr)_200px] gap-3 flex-1 min-h-0 min-w-0 overflow-hidden">
        <div className="min-h-0 min-w-0 overflow-hidden">
          <ResponsiveSvg minWidth={120} minHeight={120} className="relative">
            {({ width, height }) => (
              <PowerAnalysisBody d={d} view={view} lineOpacity={ar.opacityFor("line")} width={width} height={height} />
            )}
          </ResponsiveSvg>
        </div>
        <aside className="flex min-h-0 min-w-0 flex-col gap-3 overflow-hidden">
          <SegmentedControl size="md" bordered value={view} onChange={(v) => setView(v as any)}
            options={[{ value: "active-reactive", label: String(d.activeReactiveToggleLabel ?? "Active / Reactive") },
                      { value: "demand", label: String(d.demandToggleLabel ?? "Demand Profile") }]} />
          {view === "demand" ? (
            <div className="flex flex-col gap-3 pt-1">
              {arr(d.demandBandLegend).map((it: any) => (
                <InteractiveLegendRow key={String(it?.band)} color={it?.color} label={`${it?.label ?? it?.band ?? ""}  ${it?.threshold ?? ""}`}
                  checked={!!demand.focused[it?.band]} onToggle={() => demand.toggle(it?.band)} />
              ))}
            </div>
          ) : (
            <>
              <InteractiveLegendRow color={d.activeColor} label={String(d.activeLegendLabel ?? "Active")}
                value={fmtNum(d.activePowerAvgKw, 1)} unit={d.activeLegendUnit}
                checked={ar.focused.active} onToggle={() => ar.toggle("active")} />
              <InteractiveLegendRow color={d.reactiveColor} label={String(d.reactiveLegendLabel ?? "Reactive")}
                value={fmtNum(d.reactivePowerAvgKw, 1)} unit={d.reactiveLegendUnit}
                checked={ar.focused.reactive} onToggle={() => ar.toggle("reactive")} />
              <InteractiveLegendRow color={d.averageColor} label={String(d.averageLegendLabel ?? "Average")} swatch="line"
                checked={ar.focused.line} onToggle={() => ar.toggle("line")} />
            </>
          )}
          {d.insight ? (
            <div className="flex min-h-0 flex-1 flex-col justify-end">
              <div className="scroll-on-hover min-h-0 overflow-y-auto"><AiSummary text={String(d.insight)} className="w-full" /></div>
            </div>
          ) : null}
        </aside>
      </div>
    </Card>
  );
}

// ── Cards 16/17 — roster-generic trend / demand charts (view.points + view.legend by KEY) ─────────────────────────
// Series roster+order+colour ride the payload (view.legend); the accessor is fieldOf(point, row.id) so per-feeder
// index-signature keys AND canonical keys both render. 16 stacks bars; 17 draws one line per roster row.
function RosterChartBody({ view, points, legend, kind, refValue, refLabel, refUnit, width, height }: {
  view: any; points: any[]; legend: any[]; kind: "bars" | "lines";
  refValue?: number | null; refLabel?: string; refUnit?: string; width: number; height: number;
}) {
  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right);
  const innerH = Math.max(0, height - MARGIN.top - MARGIN.bottom);
  // domain from the roster values actually present: bars → max stacked column sum; lines → max/min single value.
  let lo = 0, hi = 0;
  for (const p of points) {
    if (kind === "bars") {
      let sum = 0;
      for (const r of legend) sum += fieldOf(p, r?.id) ?? 0;
      hi = Math.max(hi, sum);
    } else {
      for (const r of legend) {
        const v = fieldOf(p, r?.id);
        if (v == null) continue;
        hi = Math.max(hi, v); lo = Math.min(lo, v);
      }
    }
  }
  if (refValue != null && refValue > hi) hi = refValue;
  const yMin = Math.min(0, lo), yMax = hi > yMin ? hi : yMin + 1;
  const yRange = yMax - yMin || 1;
  const yScale = (v: number) => innerH - ((v - yMin) / yRange) * innerH;
  const xSpacing = points.length > 0 ? innerW / points.length : 0;
  const xCenter = (i: number) => xSpacing * (i + 0.5);
  const barW = Math.max(6, Math.min(18, xSpacing * 0.5));
  const yTicks = niceTicks(yMin, yMax, 6).map((v) => ({ y: yScale(v), label: String(v) }));
  const xTicks = sparseTickIndexes(points.length, Math.max(2, Math.floor(innerW / 48)))
    .map((i) => ({ x: xCenter(i), label: String(points[i]?.label ?? "") }));

  return (
    <ChartFrame width={width} height={height} margin={MARGIN}>
      {(plot) => (
        <>
          <GridAxis plot={plot} xTicks={xTicks} yTicks={yTicks} {...axisProps(view?.yAxisTitle ? String(view.yAxisTitle) : undefined)} />
          {refValue != null && refValue > 0 && (
            <ReferenceLine plot={plot} y={yScale(refValue)} tone="watch" placement="above"
              label={`${refLabel ?? "Limit"}: ${composeValueUnit(String(refValue), refUnit, " ")}`} />
          )}
          {kind === "bars" ? (
            <StackedBars plot={plot} barWidth={barW} segmentRadius={2}
              bars={points.map((p, i) => ({
                id: `p-${i}`, x: xCenter(i),
                segments: buildDivergingSegments(
                  legend.map((r) => ({ id: r?.id, value: fieldOf(p, r?.id) ?? 0, color: r?.color ?? CHART_COLORS.teal500 })),
                  yScale, { plotTop: MARGIN.top, innerHeight: innerH }),
              }))} />
          ) : (
            legend.map((r) => (
              <LinePath key={String(r?.id)} plot={plot} stroke={r?.color ?? CHART_COLORS.teal500} strokeWidth={2} markerRadius={0}
                points={points.map((p, i) => ({ x: xCenter(i), y: (() => { const v = fieldOf(p, r?.id); return v == null ? null : Math.max(0, Math.min(innerH, yScale(v))); })() }))} />
            ))
          )}
        </>
      )}
    </ChartFrame>
  );
}

export function EnergyTrend16({ payload, onDateChange }: { payload: any; onDateChange?: (dw: DateWindow) => void }) {
  const view = payload?.view ?? payload?.data ?? payload ?? {};
  const [split, setSplit] = React.useState<string>(view.splitView === "equipment" ? "equipment" : "total");
  const [sampling, setSampling] = useSampling(undefined);
  const legendRows = arr(split === "total" ? view.legend : (view.totalLegend ?? view.legend));
  const legendKeys = legendRows.flatMap((r: any) => [r?.id, ...arr(r?.subRows).map((s: any) => s?.id)]).filter(Boolean);
  const legend = useInteractiveLegend<string>(legendKeys.length ? legendKeys : ["_"]);
  const totals = arr(view.totals);
  return (
    <Card className="h-full gap-3" overflow="hidden" style={{ padding: 12 }}>
      <CardHeader title={dash(view.title)} action={
        <div className="flex items-center gap-1.5">
          <PickerAction sampling={sampling} setSampling={setSampling} presets={view.rangeOptions}
            resolutionOptions={view.resolutionOptions} shiftOptions={view.shiftOptions} onDateChange={onDateChange} />
          {arr(view.splitOptions).length ? (
            <SegmentedControl size="sm" value={split} onChange={setSplit} options={view.splitOptions} />
          ) : null}
        </div>
      } />
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_200px] gap-3">
        <div className="flex min-h-0 flex-col gap-2">
          {totals.length ? (
            <div className="flex flex-wrap items-center gap-2 text-[10px]">
              {view.totalLabel ? <span className="font-semibold" style={{ opacity: 0.6 }}>{String(view.totalLabel)}</span> : null}
              {totals.map((t: any, i: number) => (
                <span key={i} className="rounded-[2px] px-2 py-0.5"
                  style={{ background: t?.tone === "warning" ? CHART_COLORS.coral100 : CHART_COLORS.cream100,
                           color: t?.tone === "warning" ? CHART_COLORS.coral500 : undefined }}>{dash(t?.value)}</span>
              ))}
            </div>
          ) : null}
          <div className="min-h-0 flex-1">
            <ResponsiveSvg minWidth={120} minHeight={120}>
              {({ width, height }) => (
                <RosterChartBody view={view} points={arr(view.points)} legend={legendRows} kind="bars"
                  width={width} height={height} />
              )}
            </ResponsiveSvg>
          </div>
        </div>
        <aside className="flex min-h-0 flex-col gap-3 border-l pl-3" style={{ borderColor: CHART_COLORS.cream400 }}>
          <ExpandableLegend rows={legendRows as any} focused={legend.focused} onToggle={legend.toggle} swatch="square" wrapLabels />
          {view.insight ? <AiSummary text={String(view.insight)} density="compact" className="mt-auto" /> : null}
        </aside>
      </div>
    </Card>
  );
}

export function DemandProfile17({ payload, onDateChange }: { payload: any; onDateChange?: (dw: DateWindow) => void }) {
  const view = payload?.view ?? payload?.data ?? payload ?? {};
  const [sampling, setSampling] = useSampling(undefined);
  const legendRows = arr(view.legend);
  const legendKeys = legendRows.flatMap((r: any) => [r?.id, ...arr(r?.subRows).map((s: any) => s?.id)]).filter(Boolean);
  const legend = useInteractiveLegend<string>(legendKeys.length ? legendKeys : ["_"]);
  const stats = arr(view.stats);
  return (
    <Card className="h-full gap-3" overflow="hidden" style={{ padding: 12 }}>
      <CardHeader title={dash(view.title)} action={
        <PickerAction sampling={sampling} setSampling={setSampling} presets={view.rangeOptions}
          resolutionOptions={view.resolutionOptions} shiftOptions={view.shiftOptions} onDateChange={onDateChange} />
      } />
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_200px] gap-3">
        <div className="flex min-h-0 flex-col">
          {stats.length ? (
            <KpiStatStrip cells={stats.map((s: any) => ({ id: String(s?.id ?? s?.label), label: String(s?.label ?? ""),
              value: dash(s?.value), unit: s?.unit, sub: s?.sub }))} />
          ) : null}
          <div className="min-h-0 flex-1">
            <ResponsiveSvg minWidth={120} minHeight={120}>
              {({ width, height }) => (
                <RosterChartBody view={view} points={arr(view.points)} legend={legendRows} kind="lines"
                  refValue={fin(view.criticalKw)} refLabel={view.criticalLabel} refUnit={view.criticalUnit ?? "kW"}
                  width={width} height={height} />
              )}
            </ResponsiveSvg>
          </div>
        </div>
        <aside className="flex min-h-0 flex-col gap-3 border-l pl-3" style={{ borderColor: CHART_COLORS.cream400 }}>
          <ExpandableLegend rows={legendRows as any} focused={legend.focused} onToggle={legend.toggle} swatch="line-plain" wrapLabels />
          {view.insight ? <AiSummary text={String(view.insight)} density="compact" className="mt-auto" /> : null}
        </aside>
      </div>
    </Card>
  );
}
