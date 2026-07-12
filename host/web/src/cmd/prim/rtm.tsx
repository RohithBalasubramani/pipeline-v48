// prim/rtm.tsx — Real-Time Monitoring family (cards 7, 9, 10, 11, 36, 37, 38) on PRIMITIVES ONLY. [primitives-only port]
//
// Every card mounts CMD_V2 chart PRIMITIVES directly from its completed payload; header/legends/colors/values ride the
// payload (AI-morphable). Two pages feed this file:
//   • panel-overview real-time-monitoring — the "context rail" (7 = rail composite; 9/10/11 = its supply / trend /
//     quick-stats sub-cards standalone). Recomposed from Card/CardHeader/AiSummary/StatusPill/SegmentBar/KpiMiniCard +
//     a LinePath sparkline (the page card HAND-DREW an inline SVG sparkline — replaced with the barrel LinePath).
//   • individual-feeder real-time-monitoring — 36 = Power & Energy (recomposed from ChartFrame/GridAxis/LinePath/
//     InteractiveLegendRow/LiveTag, mirroring the page's PowerEnergyChart+PowerEnergyRail), 37/38 = Voltage/Current
//     monitor (PhaseMonitorPanel IS a barrel primitive → mounted directly with the payload `data` spread).
//
// HONESTY: a missing scalar renders '—' via dash()/fmtNum(); a missing list renders empty chrome; thresholds with no
// finite value are dropped (never a NaN reference line); tone lookups fall back to the least-assertive 'info' — never a
// record-miss crash. No fabricated points. NOTE: the guard tier already dashes null scalars and normalizes freshness/
// badge tones before this file sees the payload, but every read here is defensive anyway (per PORT_CONTRACT rule 4).
import React from "react";
import {
  AiSummary,
  Card,
  CardBodySkeleton,
  CardHeader,
  ChartFrame,
  composeMetricText,
  composeValueUnit,
  GridAxis,
  InteractiveLegendRow,
  KpiMiniCard,
  LinePath,
  LiveTag,
  PhaseMonitorPanel,
  ResponsiveSvg,
  SegmentBar,
  StatusPill,
  useInteractiveLegend,
  CHART_COLORS,
  CHART_MARGIN,
  POWER_METRICS,
} from "@cmd-v2/components/charts/primitives";
import { dash, fin, fmtNum } from "./shared";

// StatusPill's own tone enum (the guard tier normalizes a served tone into this set; this is the render-leaf fallback so
// an unexpected value degrades to the least-assertive 'info' instead of indexing STATUS_PILL_TONES[undefined]).
const DS_PILL_TONES = new Set(["normal", "alarm", "watch", "info"]);
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

/** #rrggbb → rgba() with alpha (energy legend swatches, mirroring PowerEnergyRail). Non-hex passes through. */
function alpha(hex: string, a: number): string {
  if (typeof hex !== "string" || !hex.startsWith("#") || hex.length !== 7) return hex;
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

/** A rail trend/status badge → StatusPill. Word precedence text > vocab[key] > label; tone from the DS `dsTone` seam. */
function RailPill({ badge }: { badge: any }) {
  if (!badge || typeof badge !== "object") return null;
  const word = badge.text || (badge.key != null ? badge.vocab?.[badge.key] : undefined) || badge.label;
  const tone = DS_PILL_TONES.has(badge.dsTone) ? badge.dsTone : "info";
  return <StatusPill label={dash(word)} tone={tone as any} />;
}

/** A structured (MetricText) or plain-string label → its composed string. */
const labelText = (l: any): string => (l && typeof l === "object" ? composeMetricText(l) : dash(l));

// ── card 9 / rail supply block ────────────────────────────────────────────────────────────────────────────────────
// headline `value / denominator unit` + optional delta + optional consumed hint + breakdown SegmentBar with legend.
function SupplyContent({ supply }: { supply: any }) {
  const s = supply ?? {};
  const unit = s.unit || undefined;
  const denomDisplay = fin(s.denominator) != null ? fmtNum(s.denominator, 0) : dash(s.denominator);
  const breakdown = Array.isArray(s.breakdown) ? s.breakdown.filter((b: any) => b && fin(b.value) != null) : [];
  const hint = s.consumedHint; // guard excludes *hint keys → stays null when unmeasured
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline gap-1">
        <span className="text-[20px] font-semibold leading-none">{fmtNum(s.value, 0)}</span>
        <span className="text-[12px] opacity-60">/ {composeValueUnit(denomDisplay, unit)}</span>
      </div>
      {s.delta ? (
        <div className="flex items-center gap-1 text-[11px] opacity-70">
          {s.deltaGlyph ? <span style={{ color: s.deltaColor }}>{s.deltaGlyph}</span> : null}
          <span>{labelText(s.delta)}</span>
        </div>
      ) : null}
      {hint && typeof hint === "object" ? (
        <div className="flex items-center justify-between text-[12px] opacity-70">
          <span>{fmtNum(hint.consumedPct, 0, hint.percentUnit)} {hint.consumedLabel ?? ""}</span>
          <span>{composeValueUnit(fmtNum(hint.leftKw, 0), unit)} {hint.leftLabel ?? ""}</span>
        </div>
      ) : null}
      {breakdown.length ? (
        <>
          <SegmentBar segments={breakdown.map((b: any, i: number) => ({ key: String(b.id ?? i), value: fin(b.value) ?? 0, color: b.color }))} />
          <div className="flex flex-col gap-1 text-[12px]">
            {breakdown.map((b: any, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <span className="size-2 shrink-0 rounded-sm" style={{ background: b.color }} />
                <span className="flex-1 opacity-70">{dash(b.label)}</span>
                <span className="font-semibold">{composeValueUnit(fmtNum(b.value), b.unit)}</span>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

// ── card 10 / rail trend block ────────────────────────────────────────────────────────────────────────────────────
// LinePath sparkline (barrel — replaces the page card's hand-drawn inline <path>) + bottom-stat strip.
function Sparkline({ series, color }: { series: any[]; color?: string }) {
  const raw = Array.isArray(series) ? series : [];
  const nums = raw.map((v) => fin(v)).filter((v): v is number => v != null);
  const w = 270, h = 44;
  if (nums.length < 2) return <div style={{ height: h }} />; // honest empty chrome — no fabricated flat line
  const min = Math.min(...nums), max = Math.max(...nums);
  const range = Math.max(1e-9, max - min);
  const stroke = color || POWER_METRICS.active;
  return (
    <ChartFrame width={w} height={h} margin={{ top: 4, right: 2, bottom: 4, left: 2 }} className="w-full">
      {(plot) => {
        const pts = raw.map((v, i) => {
          const n = fin(v);
          const x = raw.length > 1 ? (i / (raw.length - 1)) * plot.innerWidth : 0;
          return { x, y: n == null ? null : plot.innerHeight - ((n - min) / range) * plot.innerHeight };
        });
        return <LinePath plot={plot} points={pts as any} stroke={stroke} strokeWidth={1.5} curve="smooth" markerRadius={2} markerFill={stroke} />;
      }}
    </ChartFrame>
  );
}

function TrendContent({ trend }: { trend: any }) {
  const t = trend ?? {};
  const stats = Array.isArray(t.bottomStats) ? t.bottomStats : [];
  return (
    <div className="flex flex-col gap-2">
      <Sparkline series={t.series} color={t.lineColor} />
      {stats.length ? (
        <div className="flex items-stretch gap-3">
          {stats.map((stat: any, i: number) => (
            <div key={i} className="flex flex-1 flex-col gap-1">
              <div className="text-[12px] opacity-60">{dash(stat.label)}</div>
              <div className="flex items-baseline gap-1">
                <span className="text-[16px] font-semibold leading-none">{dash(stat.value)}</span>
                {stat.unit ? <span className="text-[12px] opacity-70">{stat.unit}</span> : null}
              </div>
              {stat.subtext ? <div className="text-[11px] opacity-60">{stat.subtext}</div> : null}
              {stat.trend && typeof stat.trend === "object" ? (
                <div className="flex items-center gap-1 text-[11px]" style={{ color: stat.trend.color }}>
                  {stat.trend.glyph ? <span style={{ color: stat.trend.glyphColor ?? stat.trend.color }}>{stat.trend.glyph}</span> : null}
                  <span>{labelText(stat.trend.label)}</span>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ── card 11 / rail quick-stats block ──────────────────────────────────────────────────────────────────────────────
function QuickStatsGrid({ stats, layout }: { stats: any[]; layout?: string }) {
  const rows = Array.isArray(stats) ? stats : [];
  return (
    <div className={layout === "stack" ? "flex flex-col gap-2.5" : "grid grid-cols-2 gap-2.5"}>
      {rows.map((s: any, i: number) => {
        const tr = s.trend && typeof s.trend === "object"
          ? { label: labelText(s.trend.label), color: s.trend.color, arrow: s.trend.glyph }
          : undefined;
        return <KpiMiniCard key={i} label={dash(s.label)} value={dash(s.value)} unit={s.unit || undefined} trend={tr as any} />;
      })}
    </div>
  );
}

/** Bordered sub-box for the card-7 rail (mirrors the page card's RailCard chrome). */
function RailSection({ title, action, children }: { title?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="flex shrink-0 flex-col gap-2 rounded-[8px] border p-2.5" style={{ borderColor: CHART_COLORS.cream400 }}>
      {(title != null || action) ? (
        <div className="flex items-center justify-between gap-2">
          {title != null ? <div className="text-[14px] opacity-80">{dash(title)}</div> : <span />}
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

// ── card 36 — Power & Energy (recomposed from ChartFrame/GridAxis/LinePath/InteractiveLegendRow/LiveTag) ────────────
function PowerEnergyChartMini({ data, opacities }: { data: any; opacities: number[] }) {
  const series: any[] = Array.isArray(data.dataSeries) ? data.dataSeries : [];
  const yLabels: string[] = Array.isArray(data.yLabels) ? data.yLabels : [];
  const sampleTs: any[] = Array.isArray(data.sampleTimestamps) ? data.sampleTimestamps : [];
  const timeLabels: string[] = Array.isArray(data.timeLabels) ? data.timeLabels : [];
  const timeTs: any[] = Array.isArray(data.timeLabelTimestamps) ? data.timeLabelTimestamps : [];
  const startMs = fin(data.axisStartMs) ?? 0, endMs = fin(data.axisEndMs) ?? 0;
  const colors = [POWER_METRICS.active, POWER_METRICS.reactive];
  return (
    <ResponsiveSvg minWidth={160} minHeight={120}>
      {({ width, height }) => (
        <ChartFrame width={width} height={height} margin={CHART_MARGIN.withYTitle}>
          {(plot) => {
            const { innerWidth, innerHeight } = plot;
            const domain = endMs - startMs;
            const xByTime = (ts: number) => (domain > 0 ? ((ts - startMs) / domain) * innerWidth : 0);
            const yScale = (v: number) => innerHeight - clamp01(v) * innerHeight;
            const yTicks = yLabels.map((label, i) => ({ y: yLabels.length > 1 ? (i / (yLabels.length - 1)) * innerHeight : 0, label }));
            const xTicks: { x: number; label: string }[] = [];
            for (let i = 0; i < Math.min(timeLabels.length, timeTs.length); i++) {
              const ts = fin(timeTs[i]);
              if (ts != null) xTicks.push({ x: xByTime(ts), label: timeLabels[i] });
            }
            return (
              <>
                <GridAxis plot={plot} xTicks={xTicks} yTicks={yTicks} showHorizontalGrid
                  yAxisLabel={data.yAxisLabel} xAxisLabel={data.xAxisLabel}
                  labelColor={CHART_COLORS.teal500} yAxisTitleOffset={50} xAxisTitleOffset={22} />
                {series.slice(0, 2).map((vals: any[], k: number) => {
                  const arr = Array.isArray(vals) ? vals : [];
                  const pts: any[] = [];
                  for (let i = 0; i < Math.min(arr.length, sampleTs.length); i++) {
                    const ts = fin(sampleTs[i]);
                    if (ts == null) continue;
                    const v = fin(arr[i]);
                    pts.push({ x: xByTime(ts), y: v == null ? null : yScale(v) });
                  }
                  return <LinePath key={k} plot={plot} points={pts} stroke={colors[k] ?? POWER_METRICS.active} strokeWidth={2} curve="smooth" opacity={opacities[k] ?? 1} />;
                })}
              </>
            );
          }}
        </ChartFrame>
      )}
    </ResponsiveSvg>
  );
}

/** One right-rail scalar row (Projected / Apparent / dKW-dt / kVAR-Trend). */
function RailMetric({ label, value }: { label: any; value: string }) {
  return (
    <div className="flex justify-between gap-2 text-[12px]">
      <span className="opacity-70">{dash(label)}</span>
      <span className="w-[100px] text-right font-semibold">{value}</span>
    </div>
  );
}

const readingDisplay = (r: any): string => (r && typeof r === "object" ? composeValueUnit(dash(r.displayValue), r.unit) : "—");
const kvarTrendText = (readings: any): string => {
  const dir = readings?.reactivePowerTrend;
  const glyph = dir === "rising" ? "↑ " : dir === "falling" ? "↓ " : "";
  return `${glyph}${dash(readings?.reactivePowerTrendLabel)}`;
};

function PowerEnergyPanelPrim({ p }: { p: any }) {
  const data = p?.data ?? {};
  const fresh = p?.freshness ?? {};
  const readings = data.readings ?? {};
  const railLabels = data.railLabels ?? {};
  const keys = ["activePower", "reactivePower", "activeEnergy", "reactiveEnergy"];
  const { focused, toggle, opacityFor } = useInteractiveLegend<string>(keys);
  if (p?.loading) {
    return (
      <Card className="h-full gap-3">
        <CardHeader title={dash(data.title)} action={<LiveTag label={fresh.label ?? undefined} tone={fresh.tone ?? undefined} title={fresh.title ?? undefined} />} actionPlacement="inline" />
        <CardBodySkeleton rail railRows={6} />
      </Card>
    );
  }
  const legendRows = [
    { key: "activePower", color: POWER_METRICS.active, r: readings.activePower },
    { key: "reactivePower", color: POWER_METRICS.reactive, r: readings.reactivePower },
    { key: "activeEnergy", color: alpha(POWER_METRICS.active, 0.35), r: readings.activeEnergy },
    { key: "reactiveEnergy", color: alpha(POWER_METRICS.reactive, 0.35), r: readings.reactiveEnergy },
  ];
  const opacities = [opacityFor("activePower"), opacityFor("reactivePower")];
  return (
    <Card className="h-full gap-3">
      <CardHeader
        title={(
          <span className="inline-flex min-w-0 items-center gap-[10px]">
            <span className="truncate">{dash(data.title)}</span>
            <LiveTag label={fresh.label ?? undefined} tone={fresh.tone ?? undefined} title={fresh.title ?? undefined} />
          </span>
        )}
        actionPlacement="inline"
      />
      <div className="flex min-h-0 flex-1 gap-3">
        <div className="min-w-0 flex-1"><PowerEnergyChartMini data={data} opacities={opacities} /></div>
        <div className="flex min-h-0 w-[209px] shrink-0 flex-col gap-3 overflow-y-auto border-l pl-3 pr-1" style={{ borderColor: CHART_COLORS.cream400 }}>
          <div className="flex flex-col gap-3 border-b pb-4" style={{ borderColor: CHART_COLORS.cream400 }}>
            {legendRows.map((row) => {
              const r = row.r ?? {};
              return (
                <InteractiveLegendRow key={row.key} color={row.color} label={dash(r.label) === "—" ? row.key : String(r.label)}
                  value={r.displayValue != null ? String(r.displayValue) : undefined} unit={r.unit || undefined}
                  checked={focused[row.key] ?? false} onToggle={() => toggle(row.key)} />
              );
            })}
          </div>
          <div className="flex flex-col gap-3">
            <RailMetric label={railLabels.projected} value={readingDisplay(readings.projectedDemand)} />
            <RailMetric label={railLabels.apparent} value={readingDisplay(readings.apparentPower)} />
            <RailMetric label={railLabels.dkwDt} value={dash(readings.activePowerDeltaPerMinute)} />
            <RailMetric label={railLabels.kvarTrend} value={kvarTrendText(readings)} />
          </div>
        </div>
      </div>
    </Card>
  );
}

// ── cards 37 / 38 — PhaseMonitorPanel (barrel primitive) mounted directly with the payload `data` spread ────────────
function phaseProps(p: any) {
  const d = p?.data ?? {};
  const f = p?.freshness ?? {};
  // Drop non-finite thresholds so no reference line lands at yScale('—')=NaN (the guard dashed unmeasured leaves to '—').
  const thresholds = (Array.isArray(d.thresholds) ? d.thresholds : [])
    .filter((t: any) => t && fin(t.value) != null)
    .map((t: any) => ({ label: String(t.label ?? ""), value: fin(t.value) as number }));
  return {
    title: dash(d.title),
    series: Array.isArray(d.series) ? d.series : [],
    yTicks: Array.isArray(d.yTicks) ? d.yTicks : [],
    yAxisLabel: d.yAxisLabel ?? "",
    xAxisLabel: d.xAxisLabel,
    timeLabels: Array.isArray(d.timeLabels) ? d.timeLabels : [],
    timeLabelTimestamps: Array.isArray(d.timeLabelTimestamps) ? d.timeLabelTimestamps : [],
    sampleTimestamps: Array.isArray(d.sampleTimestamps) ? d.sampleTimestamps : [],
    axisStartMs: fin(d.axisStartMs) ?? 0,
    axisEndMs: fin(d.axisEndMs) ?? 0,
    thresholds,
    legendItems: Array.isArray(d.legendItems) ? d.legendItems : [],
    metrics: Array.isArray(d.metrics) ? d.metrics : [],
    liveLabel: f.label ?? undefined,
    liveTone: (f.tone ?? undefined) as any,
    liveTitle: f.title ?? undefined,
  };
}

export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  // 7 — context rail composite (AI + supply + trend + quick-stats).
  7: (p) => {
    const vm = p?.railVM ?? {};
    return (
      <Card className="h-full w-[300px] shrink-0" style={{ padding: 12, gap: 12 }}>
        <CardHeader title={dash(vm.title)} action={<RailPill badge={vm.statusBadge} />} />
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
          <AiSummary text={dash(vm.aiSummaryText)} density="compact" />
          {vm.supply ? <RailSection title={vm.supply.title}><SupplyContent supply={vm.supply} /></RailSection> : null}
          {vm.trend ? <RailSection title={vm.trend.title} action={<RailPill badge={vm.trend.statusBadge} />}><TrendContent trend={vm.trend} /></RailSection> : null}
          {Array.isArray(vm.quickStats) && vm.quickStats.length ? <QuickStatsGrid stats={vm.quickStats} layout={vm.quickStatsLayout} /> : null}
        </div>
      </Card>
    );
  },
  // 9 — Total feeder consumption / supply.
  9: (p) => (
    <Card className="h-full gap-2" style={{ padding: "8px 12px" }}>
      <CardHeader title={dash(p?.supply?.title)} />
      <div className="min-h-0 flex-1"><SupplyContent supply={p?.supply} /></div>
    </Card>
  ),
  // 10 — Consumption / supply trend (sparkline).
  10: (p) => (
    <Card className="h-full gap-2" style={{ padding: "8px 12px" }}>
      <CardHeader title={dash(p?.trend?.title)} action={<RailPill badge={p?.trend?.statusBadge} />} />
      <div className="min-h-0 flex-1"><TrendContent trend={p?.trend} /></div>
    </Card>
  ),
  // 11 — Quick stats grid.
  11: (p) => (
    <Card className="h-full justify-center" style={{ padding: "8px 12px" }}>
      <QuickStatsGrid stats={p?.stats} layout={p?.layout} />
    </Card>
  ),
  // 36 — Power & Energy (real-time).
  36: (p) => <PowerEnergyPanelPrim p={p} />,
  // 37 / 38 — Voltage / Current monitor (PhaseMonitorPanel barrel primitive).
  37: (p) => <PhaseMonitorPanel {...phaseProps(p)} />,
  38: (p) => <PhaseMonitorPanel {...phaseProps(p)} />,
};
