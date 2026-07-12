// prim/ups.tsx — UPS asset dashboard (cards 50-59) on PRIMITIVES ONLY. [primitives-only port]
//
// Every card mounts CMD_V2 chart primitives directly from its completed payload; header/values/colors ride the
// payload (AI-morphable). The family reduces to five arrangements (docs/primitives_inventory/ups.md §5):
//   50/52/54/57  progress-KPI card   → ProgressKpiCard + FillBar (marker/badge) + KpiStatStrip + AiSummary
//   51/53        score-history line  → ChartFrame/GridAxis/LinePath/HorizontalBand/ReferenceLine + InteractiveLegendRow
//   55           activity tick strip → honest boolean[] strip (chrome, not fabricated data)
//   58           bar-sparkline KPI   → ProgressKpiCard + StackedBars sparkline
//   56/59        dual-axis composite → the shared CompositeChartCard primitive (adapter injects the g13 sampling default)
// HONESTY: missing scalar → '—' (fin/dash/fmtNum); tone lookups fall back to a neutral tone (STATUS_PILL_TONES record-miss
// was a crash class — see §6); status dots render only when a statusLabel is present; blank buckets draw NO bar/point.
import React, { useState } from "react";
import {
  AiSummary, Card, CardHeader, CardBodySkeleton, StatusPill, STATUS_PILL_TONES, type StatusPillTone,
  FillBar, KpiStatStrip, type KpiStatCell, ProgressKpiCard,
  ChartFrame, GridAxis, LinePath, type PlotPoint, HorizontalBand, ReferenceLine, ResponsiveSvg,
  InteractiveLegendRow, useInteractiveLegend, StackedBars, CompositeChartCard,
  CHART_COLORS as C, TYPOGRAPHY_FAMILY as FAM, SURFACES,
} from "@cmd-v2/components/charts/primitives";
import { fin, dash, fmtNum } from "./shared";

// ── generic guards ────────────────────────────────────────────────────────────────────────────────────────────────
/** The card's inner view object ({variant, batteryHealth} → batteryHealth); falls back to the payload itself so a
 *  spread/unwrapped shape still reads. */
const pick = (p: any, key: string): any =>
  p && typeof p === "object" && p[key] && typeof p[key] === "object" ? p[key] : (p ?? {});
/** Real number → cleanly formatted; blank/'—' → '—'; a non-numeric string (a mode name) passes through unblanked. */
const cellVal = (v: any): string => (fin(v) != null ? fmtNum(v) : dash(v));
const pctOf = (v: any): number => fin(v) ?? 0;
const arr = (v: any): any[] => (Array.isArray(v) ? v : []);
// Domain + DS tone strings → a valid StatusPillTone; ANY unknown/empty tone → neutral 'info' (never a record-miss).
const TONE: Record<string, StatusPillTone> = {
  success: "normal", warning: "watch", danger: "alarm", positive: "normal", negative: "alarm", neutral: "info",
  normal: "normal", watch: "watch", alarm: "alarm", info: "info",
};
const toneOf = (t: any): StatusPillTone => TONE[String(t ?? "")] ?? "info";
const CAP = { fontFamily: FAM.spaceMono, fontSize: 12, color: C.sky400 } as const;

/** StatusPill only when the payload carries a label (empty status = no pill, not a blank chip). */
function statusPill(status: any): React.ReactNode {
  const label = String(status?.label ?? "");
  return label ? <StatusPill label={label} tone={toneOf(status?.tone)} /> : undefined;
}
/** HealthMetric[] → KpiStatStrip cells. status dot only when statusLabel present (guards KPI_STATUS_DOT_PRESETS miss). */
function metricCells(metrics: any, withStatus: boolean): KpiStatCell[] {
  return arr(metrics).map((m: any, i: number): KpiStatCell => {
    const sl = String(m?.statusLabel ?? "");
    return {
      id: String(m?.label ?? i), label: String(m?.label ?? ""), value: cellVal(m?.value),
      unit: m?.unit || undefined, unitSuffix: m?.unitSuffix || undefined,
      ...(withStatus && sl ? { status: { label: sl, tone: toneOf(m?.tone) } } : {}),
    };
  });
}
const scoreCells = (cells: any): KpiStatCell[] =>
  arr(cells).map((c: any, i: number): KpiStatCell => ({
    id: String(c?.id ?? i), label: String(c?.label ?? ""), value: cellVal(c?.value),
    unit: c?.unit || undefined, swatch: c?.swatch || undefined,
  }));
/** FillBar Δ badge from a delta label + tone (pill palette); null when no label. */
function deltaBadge(label: any, tone: any) {
  const s = String(label ?? "");
  if (!s) return null;
  const t = STATUS_PILL_TONES[toneOf(tone)];
  return { label: s, background: t.bg, color: t.fg };
}

// ── shared FillBar block (bar + track + optional marker/badge + a 2/3-position caption row) ──────────────────────────
function FillBarBlock({ pct, trackColor, fillColor, fillAboveMarker, markerPct, markerColor, badge, left, mid, right }: {
  pct: number; trackColor: string; fillColor: string; fillAboveMarker?: string;
  markerPct: number | null; markerColor: string; badge: any; left: string; mid: string | null; right: string;
}) {
  const mk = markerPct != null ? Math.max(0, Math.min(100, markerPct)) : null;
  return (
    <div className="flex w-full flex-col">
      <FillBar pct={pct} trackColor={trackColor} fillColor={fillColor} fillAboveMarker={fillAboveMarker} height={32}
        marker={mk != null ? { pct: mk, color: markerColor } : null} badge={badge} />
      <div className="relative mt-1 h-4" style={CAP}>
        <span className="absolute left-0">{left}</span>
        {mid != null && mk != null ? <span className="absolute -translate-x-1/2" style={{ left: `${mk}%` }}>{mid}</span> : null}
        <span className="absolute right-0">{right}</span>
      </div>
    </div>
  );
}

// ── 55 activity tick strip (honest boolean[] → colored ticks; empty → empty inset) ──────────────────────────────────
function ActivityTicks({ ticks, start, end }: { ticks: any; start: any; end: any }) {
  return (
    <div className="flex w-full flex-col gap-1">
      <div className="flex items-stretch gap-[3px] rounded-[6px] p-[5px]"
        style={{ background: C.cream50, border: `1px solid ${C.cream400}`, height: 34 }}>
        {arr(ticks).map((ev: any, i: number) => (
          <span key={i} className="flex-1 rounded-[2px]" style={{ background: ev ? C.teal500 : C.graphite100 }} />
        ))}
      </div>
      <div className="flex justify-between" style={CAP}><span>{dash(start)}</span><span>{dash(end)}</span></div>
    </div>
  );
}

// ── 58 load-history sparkline (StackedBars; a blank bucket draws NO bar) ─────────────────────────────────────────────
function LoadSparkline({ points, start, end }: { points: any; start: any; end: any }) {
  const pts = arr(points);
  const finite = pts.map((p: any) => fin(p?.loadPct)).filter((v: any): v is number => v != null);
  const maxLoad = Math.max(100, ...(finite.length ? finite : [0]));
  return (
    <div className="flex w-full flex-col gap-1">
      <div className="h-[64px] w-full rounded-[4px] border p-[4px]" style={{ background: C.cream50, borderColor: C.cream400 }}>
        <ResponsiveSvg minHeight={48}>
          {({ width, height }) => (
            <ChartFrame width={width} height={height} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
              {(plot) => {
                const slot = pts.length > 0 ? plot.innerWidth / pts.length : 0;
                const barWidth = Math.max(2, Math.min(6, slot - 1));
                const yScale = (v: number) => (maxLoad === 0 ? 0 : (v / maxLoad) * plot.innerHeight);
                const bars = pts.flatMap((p: any, i: number) => {
                  const v = fin(p?.loadPct);
                  return v == null ? [] : [{ id: String(i), x: (i + 0.5) * slot, segments: [{ height: yScale(v), color: C.teal500, topRadius: 2 }] }];
                });
                return <StackedBars plot={plot} bars={bars} barWidth={barWidth} />;
              }}
            </ChartFrame>
          )}
        </ResponsiveSvg>
      </div>
      <div className="flex justify-between" style={CAP}><span>{dash(start)}</span><span>{dash(end)}</span></div>
    </div>
  );
}

// ── 51/53 score-history line chart (reimplemented from the page card's ChartSvg on barrel primitives only) ───────────
const HIST_MARGIN = { top: 10, right: 14, bottom: 26, left: 40 };
function ScoreHistory({ d }: { d: any }) {
  const series = arr(d.series);
  const keys = series.map((s: any, i: number) => String(s?.key ?? i));
  const { focused, opacityFor, toggle } = useInteractiveLegend(keys);
  const [active, setActive] = useState<number | null>(null);
  const minY = fin(d.minY) ?? 0;
  const maxY = fin(d.maxY) ?? 100;
  const range = maxY - minY || 1;
  const len = Math.max(1, ...series.map((s: any) => arr(s?.values).length));
  const xLabels = arr(d.xLabels);
  const xIdx = arr(d.xLabelIndexes);
  const yScale = (v: number, innerH: number) => innerH - ((v - minY) / range) * innerH;
  const xScale = (i: number, innerW: number) => (len <= 1 ? innerW / 2 : (i / (len - 1)) * innerW);
  return (
    <Card className="h-full">
      <CardHeader title={dash(d.title)} action={
        <span className="flex items-center gap-2 rounded-[6px] px-3 py-1.5"
          style={{ background: C.cream100, border: `1px solid ${C.cream200}`, fontFamily: FAM.spaceMono, fontSize: 13, color: C.teal900 }}>
          Today <span style={{ fontSize: 8 }}>▾</span>
        </span>} />
      <div className="mt-2 flex min-h-0 flex-1 gap-2">
        <div className="relative min-h-0 min-w-0 flex-1" onMouseLeave={() => setActive(null)}>
          <ResponsiveSvg minWidth={200} minHeight={150}>
            {({ width, height }) => (
              <ChartFrame width={width} height={height} margin={HIST_MARGIN}>
                {(plot) => {
                  const iw = plot.innerWidth, ih = plot.innerHeight;
                  const yT = arr(d.yTicks).map((t: any) => ({ y: yScale(Number(t), ih), label: String(t) }));
                  const xT = xLabels.map((label: any, i: number) => ({ x: xScale(fin(xIdx[i]) ?? i, iw), label: String(label ?? "") }));
                  return (
                    <>
                      {arr(d.zones).map((z: any, i: number) => (
                        <HorizontalBand key={i} plot={plot} yTop={yScale(Number(z?.to), ih)} yBottom={yScale(Number(z?.from), ih)}
                          fill={String(z?.fill ?? C.cream200)} opacity={0.08} />
                      ))}
                      <GridAxis plot={plot} xTicks={xT} yTicks={yT} showHorizontalGrid showYAxisLine
                        horizontalGridDasharray="none" gridColor={C.cream200} yAxisLabel={String(d.yLabel ?? "")}
                        yAxisTitleOffset={32} labelColor={C.sky600} axisTitleColor={C.sky600} />
                      {arr(d.thresholds).flatMap((t: any, i: number) => {
                        const val = fin(t?.value);
                        return val == null ? [] : [
                          <ReferenceLine key={i} plot={plot} y={yScale(val, ih)} label={String(t?.label ?? "")}
                            color={String(t?.color ?? C.sky600)} labelColor={String(t?.labelColor ?? t?.color ?? C.sky600)}
                            labelBackground="transparent" strokeDasharray="4 4" />,
                        ];
                      })}
                      {series.map((s: any, i: number) => (
                        <LinePath key={i} plot={plot}
                          points={arr(s?.values).map((v: any, j: number): PlotPoint => ({ x: xScale(j, iw), y: fin(v) == null ? null : yScale(Number(v), ih) }))}
                          stroke={String(s?.color ?? C.sky600)} strokeWidth={s?.dashed ? 1.5 : 2} curve="smooth"
                          strokeDasharray={s?.dashed ? "5 5" : undefined} opacity={opacityFor(String(s?.key ?? i))}
                          markerRadius={arr(s?.values).length <= 2 ? 3 : 0} markerFill={String(s?.color ?? C.sky600)} />
                      ))}
                      {active != null ? (
                        <line x1={plot.innerLeft + xScale(active, iw)} x2={plot.innerLeft + xScale(active, iw)}
                          y1={plot.innerTop} y2={plot.innerTop + ih} stroke={C.sky600} strokeWidth={1} strokeDasharray="3 3" />
                      ) : null}
                      <rect x={plot.innerLeft} y={plot.innerTop} width={iw} height={ih} fill="transparent"
                        onMouseMove={(e) => {
                          const box = (e.currentTarget as any).getBoundingClientRect();
                          const i = Math.round(((e.clientX - box.left) / Math.max(1, box.width)) * (len - 1));
                          setActive(Math.max(0, Math.min(len - 1, i)));
                        }} onMouseLeave={() => setActive(null)} />
                    </>
                  );
                }}
              </ChartFrame>
            )}
          </ResponsiveSvg>
        </div>
        <div className="flex w-[200px] shrink-0 flex-col gap-3 py-3 pl-3" style={{ borderLeft: `1px dashed ${SURFACES.divider.color}` }}>
          <div className="flex min-h-0 flex-1 flex-col gap-2 border-b border-dashed pb-3" style={{ borderColor: SURFACES.divider.color }}>
            {series.map((s: any, i: number) => (
              <InteractiveLegendRow key={i} color={String(s?.color ?? C.sky600)} label={String(s?.label ?? "")}
                value={cellVal(s?.legendValue)} swatch={s?.dashed ? "line-dashed" : "line-plain"}
                checked={focused[String(s?.key ?? i)] ?? false} onToggle={() => toggle(String(s?.key ?? i))} />
            ))}
          </div>
          <AiSummary text={String(d.insight ?? "")} className="shrink-0" />
        </div>
      </div>
    </Card>
  );
}

// ── 56/59 dual-axis composite → shared CompositeChartCard (view built cleanly; g13 sampling default owned here) ──────
function composeView(c: any): any {
  const axis = (a: any) => ({
    title: String(a?.title ?? ""),
    domain: Array.isArray(a?.domain) && a.domain.length === 2 ? a.domain : [0, 100],
    ticks: arr(a?.ticks).map((t: any) => fin(t)).filter((t: any) => t != null),
  });
  const floorV = fin(c?.floor?.value);
  return {
    title: String(c?.title ?? ""),
    activeView: c?.activeView === "voltage-current" ? "voltage-current" : "transfer-score-frequency",
    kpiCells: arr(c?.kpiCells).map((k: any, i: number) => ({
      id: String(k?.id ?? i), label: String(k?.label ?? ""), value: cellVal(k?.value), unit: k?.unit || undefined, swatch: k?.swatch || undefined,
    })),
    points: arr(c?.points),
    series: arr(c?.series),
    leftAxis: axis(c?.leftAxis),
    rightAxis: axis(c?.rightAxis),
    floor: floorV != null ? { value: floorV, label: String(c?.floor?.label ?? "") } : undefined,
    legend: arr(c?.legend).map((l: any, i: number) => ({
      id: String(l?.id ?? i), label: String(l?.label ?? ""), value: cellVal(l?.value), unit: l?.unit || undefined,
      separator: l?.separator, color: String(l?.color ?? C.sky400), swatch: l?.swatch === "dashed" ? "dashed" : "solid",
    })),
    insight: String(c?.insight ?? ""),
  };
}
const Composite = (p: any) => {
  const view = composeView(pick(p, "composite"));
  return <CompositeChartCard title={view.title} view={view} sampling={{ preset: "today", range: null } as any}
    onSamplingChange={() => undefined} onViewChange={() => undefined} loading={!!p?.loading} />;
};

// ── card registry ────────────────────────────────────────────────────────────────────────────────────────────────
export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  // 50 Battery Health — SOC bar (teal/600 on cream/200) + Temp/Voltage/Current metrics.
  50: (p) => {
    const d = pick(p, "batteryHealth");
    return p?.loading ? <ProgressKpiCard title={dash(d.title)} headline={{ value: "—" }} kpiStrips={[[]]} />
      : <ProgressKpiCard title={dash(d.title)} headerAction={statusPill(d.status)}
          headline={{ value: cellVal(d.soc), target: cellVal(d.socMax), unit: d.socUnit || undefined, unitSuffix: d.socLabel || undefined }}
          progressContent={<FillBarBlock pct={pctOf(d.socPct)} trackColor={C.cream200} fillColor={C.teal600} markerPct={null}
            markerColor={C.teal900} badge={null} left={dash(d?.barTicks?.min)} mid={null} right={dash(d?.barTicks?.max)} />}
          kpiStrips={[metricCells(d.metrics, true)]} insight={String(d.insight ?? "")} />;
  },
  // 51 Battery Health History — score-history line chart.
  51: (p) => <ScoreHistory d={pick(p, "batteryHistory")} />,
  // 52 Backup Readiness — autonomy-envelope bar (sage fill / red-below-marker) + Ready marker + Δ badge.
  52: (p) => {
    const d = pick(p, "backupReadiness");
    const mk = fin(d.readyMarkerPct);
    const below = fin(d.envelopePct) != null && mk != null && Number(d.envelopePct) < mk;
    return <ProgressKpiCard title={dash(d.title)} headerAction={statusPill(d.status)}
      headline={{ value: cellVal(d.score), target: cellVal(d.scoreMax), unitSuffix: d.scoreLabel || undefined }}
      progressContent={<FillBarBlock pct={pctOf(d.envelopePct)} trackColor={C.cream200} fillColor={below ? C.coral500 : C.sage500}
        markerPct={mk} markerColor={C.teal900} badge={deltaBadge(d.deltaLabel, d.deltaTone)}
        left={dash(d?.barTicks?.min)} mid={mk != null ? `${dash(d.readyMarkerLabel)}: ${cellVal(d.readyMarkerPct)}` : null} right={dash(d?.barTicks?.max)} />}
      kpiStrips={[metricCells(d.metrics, false)]} insight={String(d.insight ?? "")} />;
  },
  // 53 Backup Readiness History — score-history line chart.
  53: (p) => <ScoreHistory d={pick(p, "backupHistory")} />,
  // 54 Transfer Readiness — score doubles as the bar pct; Input/Bypass/Sync permissive scores WITH status dots.
  54: (p) => {
    const d = pick(p, "readiness");
    const mk = fin(d.readyMarkerPct);
    const below = fin(d.score) != null && mk != null && Number(d.score) < mk;
    return <ProgressKpiCard title={dash(d.title)} headerAction={statusPill(d.status)}
      headline={{ value: cellVal(d.score), target: cellVal(d.scoreMax), unitSuffix: d.scoreLabel || undefined }}
      progressContent={<FillBarBlock pct={pctOf(d.score)} trackColor={C.cream200} fillColor={below ? C.coral500 : C.sage500}
        markerPct={mk} markerColor={C.teal900} badge={deltaBadge(d.deltaLabel, d.deltaTone)}
        left={dash(d?.barTicks?.min)} mid={mk != null ? `${dash(d.readyMarkerLabel)}: ${cellVal(d.readyMarkerPct)}` : null} right={dash(d?.barTicks?.max)} />}
      kpiStrips={[metricCells(d.metrics, true)]} insight={String(d.insight ?? "")} />;
  },
  // 55 Activity — 30-day transfer tick strip + Last/Lifetime metrics.
  55: (p) => {
    const d = pick(p, "activity");
    return <ProgressKpiCard title={dash(d.title)}
      headline={{ value: cellVal(d.count30d), target: cellVal(d.windowDays), unitSuffix: d.countLabel || undefined }}
      progressContent={<ActivityTicks ticks={d.ticks} start={d.tickStartLabel} end={d.tickEndLabel} />}
      kpiStrips={[metricCells(d.metrics, false)]} insight={String(d.insight ?? "")} />;
  },
  // 56 Source Transfer — Composite (dual-axis line + state strip).
  56: Composite,
  // 57 UPS Capacity — two-tone capacity-headroom bar (sage → sage/600 excess above the Ready marker) + score cells.
  57: (p) => {
    const d = pick(p, "capacity");
    const mk = fin(d.readyMarkerPct);
    const below = fin(d.capacityHeadroom) != null && mk != null && Number(d.capacityHeadroom) < mk;
    return <ProgressKpiCard title={dash(d.title)} headerAction={statusPill(d.status)}
      headline={{ value: cellVal(d.capacityHeadroom), target: 100, unit: "capacity headroom" }}
      progressContent={<FillBarBlock pct={pctOf(d.capacityHeadroom)} trackColor={C.cream100}
        fillColor={below ? C.coral500 : C.sage500} fillAboveMarker={C.sage600} markerPct={mk} markerColor={C.teal900}
        badge={deltaBadge(d.deltaLabel, d.deltaTone)} left="0" mid={mk != null ? `Ready: ${cellVal(d.readyMarkerPct)}` : null} right="100" />}
      kpiStrips={[scoreCells(d.scoreCells)]} kpiCellDividers insight={String(d.insight ?? "")} />;
  },
  // 58 UPS Load % — average headline + 30-bar load-history sparkline.
  58: (p) => {
    const d = pick(p, "load");
    return <ProgressKpiCard title={dash(d.title)}
      headline={{ value: cellVal(d.averageLoadPct), unit: "%", unitSuffix: d.averageLoadLabel || undefined, meta: d.sparklineMaxLabel || undefined }}
      progressContent={<LoadSparkline points={d.sparkline} start={d.sparklineStartLabel} end={d.sparklineEndLabel} />}
      kpiStrips={[scoreCells(d.scoreCells)]} kpiCellDividers insight={String(d.insight ?? "")} />;
  },
  // 59 Output Load vs. Capacity — Composite (reuses the same shared primitive).
  59: Composite,
};
