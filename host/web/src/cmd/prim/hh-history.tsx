// prim/hh-history.tsx — HistoryPanel-class (cards 44/46 feeder, 67/69 DG) on PRIMITIVES ONLY. [port]
//
// Faithful reimplementation of CMD_V2 pages/electrical/tabs/voltage-current/HistoryPanel — barrel imports only
// (the original also imported COLORS from ./constants; the ONE non-payload chrome value it used, the expected-
// range band fill, is inlined as EXPECTED_FILL = CHART_COLORS.historyExpectedRange). KpiStatStrip(data.stats) +
// a ChartFrame/GridAxis/LinePath timeline (null values break the line — gap buckets) with a HorizontalBand
// (expected range), max/min ReferenceLines and EventDots, plus an InteractiveLegendRow rail. The header
// SamplingPicker renders only when the payload carries BOTH data.sampling + data.onSamplingChange (the wrapper
// in health-history.tsx injects them from the host onDateChange). The whole SVG sits inside ResponsiveSvg, which
// renders nothing until its container is measured — so under SSR the chart body is inert and only the chrome runs.
// Honesty: non-finite reference lines / band bounds are dropped (no phantom threshold); non-numeric series points
// become gap nulls; blank stats render '—'.
import { useState } from "react";
import {
  Card,
  CardBodySkeleton,
  CHART_COLORS,
  CHART_MARGIN,
  ChartFrame,
  ChartHoverCapture,
  ChartHoverCrosshair,
  ChartHoverTooltip,
  ChartTooltipCard,
  composeMetricText,
  EventDot,
  GridAxis,
  HorizontalBand,
  InteractiveLegendRow,
  KpiStatStrip,
  LinePath,
  ReferenceLine,
  ResponsiveSvg,
  SamplingPicker,
  SURFACES,
  THRESHOLD,
  TYPOGRAPHY,
  TYPOGRAPHY_FAMILY,
  useInteractiveLegend,
} from "@cmd-v2/components/charts/primitives";

// Expected-range band fill — chrome, not payload (V&C history "expected range" color, byte-equal to the tab's
// constants.ts COLORS.expected). The original imported it from a page module; inlined here to stay barrel-only.
const EXPECTED_FILL = CHART_COLORS.historyExpectedRange;

const AXIS_STYLE = {
  tickFontSize: 12,
  tickFontWeight: 400,
  tickFontFamily: TYPOGRAPHY_FAMILY.plex,
  labelColor: CHART_COLORS.sky600,
  gridColor: CHART_COLORS.cream200,
  axisLineColor: CHART_COLORS.cream200,
} as const;
const HISTORY_CARD_STYLE = { borderRadius: 10 } as const;
const HISTORY_HEADER_TITLE_STYLE = { fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 14, fontWeight: 400, color: CHART_COLORS.teal950, lineHeight: "normal", letterSpacing: 0 } as const;
const INSIGHT_STYLE = { ...TYPOGRAPHY.insightText, color: CHART_COLORS.tealLabel600 } as const;

const dash = (v: any): string => (v == null || v === "" ? "—" : String(v));
const num = (v: any): number | null => {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));
const formatTick = (v: number, decimals?: any) => (num(decimals) && (num(decimals) as number) > 0 ? v.toFixed(num(decimals) as number) : String(Math.round(v)));
const labelText = (label: any): string => (label == null ? "" : typeof label === "string" ? label : typeof label === "object" ? composeMetricText(label) : String(label));

/** HistoryPanel — cards 44/46 (feeder) + 67/69 (DG). `data` = HistoryPanelData (+ optional sampling wiring). */
export function HistoryPanel({ data, loading = false }: { data: any; loading?: boolean }) {
  const d = data ?? {};
  const legend: any[] = Array.isArray(d.legend) ? d.legend : [];
  const legendKeys = legend.map((item: any) => item.label);
  const { focused, toggle, opacityFor } = useInteractiveLegend<string>(legendKeys);

  return (
    <Card style={HISTORY_CARD_STYLE}>
      <header className="flex shrink-0 items-start gap-2 border-b pb-2" style={{ borderColor: SURFACES.sectionDivider.color, borderStyle: SURFACES.sectionDivider.style }}>
        <div className="flex min-w-0 flex-1 items-center">
          <h3 className="min-w-0 truncate" style={HISTORY_HEADER_TITLE_STYLE}>{dash(d.title)}</h3>
        </div>
        {d.sampling && d.onSamplingChange ? (
          <SamplingPicker
            value={d.sampling}
            onChange={d.onSamplingChange}
            presets={d.samplingPresets}
            showCalendar={d.showSamplingCalendar}
            showFooterSummary={d.showSamplingFooterSummary}
            applyLabel={d.samplingApplyLabel}
            cancelLabel={d.samplingCancelLabel}
            dialogAriaLabel={d.samplingDialogAria}
            align="end"
          />
        ) : null}
      </header>

      {loading ? (
        <CardBodySkeleton kpiCells={3} rail railRows={4} className="pt-2" />
      ) : (
        <div className="flex min-h-0 flex-1 gap-4 pt-2">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
            <HistoryStats stats={Array.isArray(d.stats) ? d.stats : []} noteVocab={d.noteVocab} />
            <div className="min-h-0 flex-1">
              <ResponsiveSvg minWidth={160} minHeight={120} className={d.showHoverTooltip ? "relative" : undefined}>
                {({ width, height }: { width: number; height: number }) => (
                  <HistoryChartSvg data={d} width={width} height={height} opacityFor={opacityFor} />
                )}
              </ResponsiveSvg>
            </div>
          </div>
          <aside className="min-h-0 w-[200px] shrink-0 overflow-hidden border-l py-3 pl-3" style={{ borderColor: SURFACES.divider.color, borderStyle: SURFACES.divider.style }}>
            <div className="scroll-on-hover flex h-full min-h-0 flex-col justify-between gap-3 overflow-y-auto pr-1">
              <div className="flex shrink-0 flex-col gap-2 border-b pb-3" style={{ borderColor: SURFACES.divider.color, borderStyle: SURFACES.divider.style }}>
                {legend.map((item: any, i: number) => (
                  <InteractiveLegendRow
                    key={`${item.label}-${i}`}
                    color={item.color}
                    label={item.label}
                    value={item.value}
                    swatch={item.swatch ?? (item.shape === "dot" ? "dot" : item.label === "Expected Range" ? "square-filled" : "square")}
                    swatchOpacity={1}
                    checked={focused[item.label] ?? false}
                    onToggle={() => toggle(item.label)}
                  />
                ))}
              </div>
              <p className="w-full" style={{ ...INSIGHT_STYLE, fontSize: 12, lineHeight: 1.45 }}>{d.insight ?? ""}</p>
            </div>
          </aside>
        </div>
      )}
    </Card>
  );
}

function HistoryStats({ stats, noteVocab }: { stats: any[]; noteVocab?: Record<string, string> }) {
  return (
    <KpiStatStrip
      className="shrink-0"
      height={60}
      withBottomDivider
      withCellDividers
      cells={stats.map((stat: any, i: number) => ({
        id: `${stat.label ?? "s"}-${i}`,
        label: stat.label,
        value: dash(stat.value),
        unit: stat.unit,
        sub: noteVocab && stat.noteKey != null ? noteVocab[stat.noteKey] ?? stat.note : stat.note,
        valueSize: stat.unit ? "default" : "compact",
      }))}
    />
  );
}

function HistoryChartSvg({ data, width, height, opacityFor }: { data: any; width: number; height: number; opacityFor: (key: string) => number }) {
  const margin = CHART_MARGIN.withYTitle;
  const innerHeight = Math.max(0, height - margin.top - margin.bottom);
  const innerWidth = Math.max(0, width - margin.left - margin.right);
  const series: any[] = Array.isArray(data.series) ? data.series : [];
  const firstSeriesLength = series[0]?.values?.length ?? 1;
  const minY = num(data.minY) ?? 0;
  const maxY = num(data.maxY) ?? 1;
  const yRange = maxY - minY || 1;
  const yScale = (value: number) => innerHeight - ((value - minY) / yRange) * innerHeight;
  const xScale = (index: number) => (index / Math.max(1, firstSeriesLength - 1)) * innerWidth;

  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const hoverEnabled = data.showHoverTooltip === true;
  const activeIdx = hoverIndex != null && hoverIndex < firstSeriesLength ? hoverIndex : null;
  const tipX = margin.left + (activeIdx != null ? xScale(activeIdx) : 0);
  const yTickDec = num(data.yTickDecimals);
  const hoverRows = activeIdx != null
    ? series
        .map((s: any) => {
          const v = num(s.values?.[activeIdx]);
          return v == null ? null : { label: s.label, value: v.toLocaleString("en-IN", { maximumFractionDigits: yTickDec ?? 0 }), unit: data.hoverUnit, color: s.color };
        })
        .filter((r: any): r is any => r != null)
    : [];
  const yTicks = (Array.isArray(data.yTicks) ? data.yTicks : []).map((tick: any) => ({ y: yScale(num(tick) ?? 0), label: formatTick(num(tick) ?? 0, data.yTickDecimals) }));
  const xLabels: any[] = Array.isArray(data.xLabels) ? data.xLabels : [];
  const xLabelIndexes: any[] = Array.isArray(data.xLabelIndexes) ? data.xLabelIndexes : [];
  const xTicks = xLabels.map((label: any, index: number) => ({ x: xScale(num(xLabelIndexes[index]) ?? index), label }));

  const expMax = num(data.expectedMax);
  const expMin = num(data.expectedMin);
  const events: any[] = Array.isArray(data.events) ? data.events : [];
  const refLines = [data.maxLine, data.minLine];

  return (
    <>
      <ChartFrame width={width} height={height} margin={margin}>
        {(plot: any) => {
          const showBand = (data.showExpectedRange ?? true) && expMax != null && expMin != null;
          const expectedTop = expMax != null ? yScale(expMax) : 0;
          const expectedBottom = expMin != null ? yScale(expMin) : 0;
          const bandIntersectsPlot = expectedBottom >= 0 && expectedTop <= innerHeight;
          const expectedOpacity = opacityFor(data.expectedRangeKey ?? "Expected Range");
          return (
            <>
              {showBand && bandIntersectsPlot ? (
                <HorizontalBand plot={plot} yTop={clamp(expectedTop, 0, innerHeight)} yBottom={clamp(expectedBottom, 0, innerHeight)} fill={EXPECTED_FILL} opacity={expectedOpacity} />
              ) : null}
              <GridAxis
                plot={plot}
                xTicks={xTicks}
                yTicks={yTicks}
                showHorizontalGrid
                showVerticalGrid
                showXAxisLine
                showYAxisLine
                horizontalGridDasharray="none"
                verticalGridDasharray="none"
                gridColor={AXIS_STYLE.gridColor}
                yAxisLabel={data.yAxisLabel}
                yAxisTitleOffset={50}
                labelColor={AXIS_STYLE.labelColor}
                tickFontSize={AXIS_STYLE.tickFontSize}
                tickFontWeight={AXIS_STYLE.tickFontWeight}
                tickFontFamily={AXIS_STYLE.tickFontFamily}
                axisTitleColor={CHART_COLORS.sky600}
                axisTitleFontSize={10}
                axisTitleFontWeight={400}
                axisTitleFontFamily={TYPOGRAPHY_FAMILY.plex}
                axisLineColor={AXIS_STYLE.axisLineColor}
                xTickOffset={18}
                yTickOffset={8}
              />
              {refLines.map((line: any, li: number) => {
                const v = line ? num(line.value) : null; // drop non-finite ref lines (no phantom threshold)
                if (v == null) return null;
                const rawY = yScale(v);
                if (rawY < 0 || rawY > innerHeight) return null; // off-scale → keep chart data-first
                return (
                  <ReferenceLine key={`ref-${li}`} plot={plot} y={rawY} label={labelText(line.label)} tone="threshold" color={THRESHOLD.line} labelColor={THRESHOLD.labelText} labelBackground={THRESHOLD.labelBg} strokeDasharray="4 4" />
                );
              })}
              {series.map((s: any, si: number) => (
                <LinePath
                  key={`${s.label}-${si}`}
                  plot={plot}
                  points={(Array.isArray(s.values) ? s.values : []).map((value: any, index: number) => {
                    const n = num(value);
                    return { x: xScale(index), y: n == null ? null : yScale(n) };
                  })}
                  stroke={s.color}
                  strokeWidth={1.15}
                  curve="smooth"
                  opacity={opacityFor(s.label)}
                />
              ))}
              {events.map((event: any, ei: number) => {
                const eventSeries = series.find((s: any) => s.label === event.seriesLabel);
                const eventValue = num(eventSeries?.values?.[event.index]);
                if (eventValue == null) return null;
                const eventTypeKey = expMax != null && eventValue >= expMax ? (data.eventTypeKeys?.swell ?? "Swell events") : (data.eventTypeKeys?.sag ?? "Sag events");
                const eventOpacity = Math.max(opacityFor(event.seriesLabel), opacityFor(eventTypeKey));
                return (
                  <g key={`ev-${ei}`} opacity={eventOpacity}>
                    <EventDot plot={plot} x={xScale(event.index)} y={yScale(eventValue)} color={event.color} />
                  </g>
                );
              })}
              {hoverEnabled && activeIdx != null && (
                <ChartHoverCrosshair
                  plot={plot}
                  x={plot.innerLeft + xScale(activeIdx)}
                  dots={series
                    .map((s: any) => {
                      const v = num(s.values?.[activeIdx]);
                      return v == null ? null : { cy: plot.innerTop + yScale(v), color: s.color };
                    })
                    .filter((dot: any): dot is any => dot != null)}
                />
              )}
              {hoverEnabled && <ChartHoverCapture plot={plot} count={firstSeriesLength} onIndex={setHoverIndex} />}
            </>
          );
        }}
      </ChartFrame>
      {hoverEnabled && activeIdx != null && hoverRows.length > 0 && (
        <ChartHoverTooltip x={tipX} width={width} top={margin.top}>
          <ChartTooltipCard title={data.hoverLabels?.[activeIdx] ?? String(activeIdx)} rows={hoverRows} />
        </ChartHoverTooltip>
      )}
    </>
  );
}
