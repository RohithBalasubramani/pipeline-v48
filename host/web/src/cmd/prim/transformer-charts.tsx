// prim/transformer-charts.tsx — reusable dual-axis timeline shell for the TRANSFORMER chart cards (76/77/79/81).
// [primitives-only port] Helper module only — it exports NO `CARDS`, so prim/index.ts's glob merge skips it; the
// family registry lives in transformer.tsx which composes this shell with per-card series/axis descriptors.
//
// Grammar reproduced from the four CMD_V2 transformer chart page-cards (ThermalTimeline / InsulationAging /
// VoltageRegulation / TapActivity): ChartFrame + GridAxis (dual y) + ChartBars/LinePath/HorizontalBand/ReferenceLine
// + optional area fill + excursion dots + hand-rolled hover crosshair/tooltip, with a right sidebar of
// InteractiveLegendRows + AiSummary. Imports ONLY from the primitives barrel. Every plotted scalar rides fin() so an
// honest-blank leaf ('—'/null) becomes a LinePath GAP, never NaN geometry; EMPTY points render axis chrome only —
// NEVER a synthetic bucket (PORT_CONTRACT honesty rule + FAMILY NOTES: guard empty points with empty-chrome render).
import React, { useState } from "react";
import {
  AiSummary,
  Card,
  CardHeader,
  ChartBars,
  ChartFrame,
  CHART_COLORS as C,
  GridAxis,
  HorizontalBand,
  InteractiveLegendRow,
  LinePath,
  ReferenceLine,
  ResponsiveSvg,
  sparseTickIndexes,
  SURFACES,
  TYPOGRAPHY_FAMILY as FAM,
} from "@cmd-v2/components/charts/primitives";
import { fin } from "./shared";

// Chart-frame chrome shared by all four cards (CMD_V2 thermal-life/tap-rtcc `CHART` tokens — reproduced as a DATA
// constant here; the barrel owns the color scale, this only names the roles).
const CHROME = { grid: C.cream200, axisText: C.sky600, axisLine: C.graphite200 } as const;

export type Mark = "bar" | "line" | "line-dashed" | "step" | "step-after";
export interface Series {
  key: string;
  accessor: (p: any) => number | null;
  mark: Mark;
  axis: "left" | "right";
  color: string;
  /** Fixed bar width; when omitted a per-bucket default is computed. */
  barWidth?: number;
  strokeWidth?: number;
  /** Fixed marker radius; when omitted lines auto-mark a 1–2 bucket window. */
  markerRadius?: number;
}
export interface AxisSpec {
  min: number | null;
  max: number | null;
  ticks: any[];
  label?: string;
  /** Zero-based right axes (tap/count/faa/pct) pin the low edge to 0. */
  zeroBased?: boolean;
  fmt?: (t: number) => string;
}
export interface RefLine {
  axis: "left" | "right";
  value: number | null;
  label: string;
  color: string;
  placement?: "above" | "below" | "center";
}
export interface Band {
  axis: "left" | "right";
  top: number | null;
  bottom: number | null;
  color: string;
}
export interface AreaSpec { axis: "left" | "right"; accessor: (p: any) => number | null; color: string }
export interface DotSpec {
  axis: "left" | "right";
  accessor: (p: any) => number | null;
  when: (p: any) => boolean;
  color: string;
}
export interface TooltipRow { key: string; label: string; color: string; value: string; dashed?: boolean }
export interface ChartSpec {
  points: any[];
  labelOf: (p: any) => string;
  left: AxisSpec;
  right: AxisSpec;
  series: Series[];
  refLines?: RefLine[];
  band?: Band | null;
  area?: AreaSpec | null;
  dots?: DotSpec | null;
  /** Lines-only chart → first/last vertex pinned to the axes (card 79). */
  edgeToEdgeX?: boolean;
  marginLeft?: number;
  tooltipRows: (p: any) => TooltipRow[];
  tooltipTag?: (p: any) => string | null;
}

const BASE_MARGIN = { top: 12, right: 44, bottom: 26, left: 48 };

/** Resolve a safe y-domain: payload min/max win; else derive from the series on this side; else a degenerate [0,1].
 *  `denom` is never 0 (no NaN scaling). `ticks` are filtered to finite values INSIDE the domain (a malformed axis whose
 *  ticks carry stray out-of-range values — e.g. epoch timestamps — drops them instead of plotting garbage labels). */
function domainOf(axis: AxisSpec, points: any[], series: Series[], side: "left" | "right") {
  let dmin = fin(axis.min);
  let dmax = fin(axis.max);
  if (dmin == null || dmax == null) {
    const vals: number[] = [];
    for (const s of series) if (s.axis === side) for (const p of points) { const v = fin(s.accessor(p)); if (v != null) vals.push(v); }
    if (vals.length) { const lo = Math.min(...vals); const hi = Math.max(...vals); if (dmin == null) dmin = axis.zeroBased ? Math.min(0, lo) : lo; if (dmax == null) dmax = hi; }
  }
  if (dmin == null) dmin = 0;
  if (dmax == null) dmax = dmin + 1;
  if (axis.zeroBased && dmin > 0) dmin = 0;
  const span = dmax - dmin;
  const denom = Math.abs(span) < 1e-9 ? 1 : span;
  const finite = Number.isFinite(dmin) && Number.isFinite(dmax);
  const ticks = (Array.isArray(axis.ticks) ? axis.ticks : [])
    .map(fin)
    .filter((t): t is number => t != null && t >= dmin - 1e-6 && t <= dmax + 1e-6);
  return { dmin, dmax, denom, finite, ticks };
}

function ChartSvg({ spec, width, height, opacityForKey, activeIndex, onActiveIndex }: {
  spec: ChartSpec; width: number; height: number;
  opacityForKey: (k: string) => number; activeIndex: number | null; onActiveIndex: (i: number | null) => void;
}) {
  const margin = { ...BASE_MARGIN, left: spec.marginLeft ?? BASE_MARGIN.left };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);
  const pts = Array.isArray(spec.points) ? spec.points : [];
  const n = pts.length;
  const L = domainOf(spec.left, pts, spec.series, "left");
  const R = domainOf(spec.right, pts, spec.series, "right");
  const yOf = (side: "left" | "right") => (v: number) => {
    const d = side === "left" ? L : R;
    return innerH - ((v - d.dmin) / d.denom) * innerH;
  };
  const yL = yOf("left");
  const yR = yOf("right");
  const yAxis = (side: "left" | "right") => (side === "left" ? yL : yR);
  const xAt = spec.edgeToEdgeX
    ? (i: number) => (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW)
    : (i: number) => (n <= 0 ? 0 : ((i + 0.5) / n) * innerW);
  const line = (s: Series) => pts.map((p, i) => { const v = fin(s.accessor(p)); return { x: xAt(i), y: v == null ? null : yAxis(s.axis)(v) }; });
  const fmtTick = (a: AxisSpec, t: number) => (a.fmt ? a.fmt(t) : String(t));

  return (
    <ChartFrame width={width} height={height} margin={margin}>
      {(plot) => (
        <>
          {spec.band && fin(spec.band.top) != null && fin(spec.band.bottom) != null && (spec.band.axis === "left" ? L : R).finite ? (
            <HorizontalBand plot={plot} yTop={yAxis(spec.band.axis)(fin(spec.band.top)!)} yBottom={yAxis(spec.band.axis)(fin(spec.band.bottom)!)} fill={spec.band.color} opacity={0.12} />
          ) : null}
          {(spec.refLines ?? []).map((r, i) => (fin(r.value) != null && (r.axis === "left" ? L : R).finite ? (
            <ReferenceLine key={`ref-${i}`} plot={plot} y={yAxis(r.axis)(fin(r.value)!)} label={r.label} color={r.color} labelColor={r.color} labelBackground={SURFACES.card.bg} placement={r.placement} strokeDasharray="4 4" />
          ) : null))}
          <GridAxis
            plot={plot}
            xTicks={n > 0 ? sparseTickIndexes(n).map((i) => ({ x: xAt(i), label: String(spec.labelOf(pts[i]) ?? "") })) : []}
            yTicks={L.finite ? L.ticks.map((t) => ({ y: yL(t), label: fmtTick(spec.left, t) })) : []}
            rightYTicks={R.finite ? R.ticks.map((t) => ({ y: yR(t), label: fmtTick(spec.right, t) })) : []}
            showHorizontalGrid showYAxisLine showRightYAxisLine
            axisLineColor={CHROME.axisLine} horizontalGridDasharray="none" gridColor={CHROME.grid}
            yAxisLabel={spec.left.label} rightYAxisLabel={spec.right.label}
            yAxisTitleOffset={spec.marginLeft && spec.marginLeft >= 56 ? 50 : 32} rightYAxisTitleOffset={32}
            labelColor={CHROME.axisText} tickFontSize={12} tickFontFamily={FAM.plex}
            axisTitleColor={CHROME.axisText} axisTitleFontSize={10} axisTitleFontFamily={FAM.plex}
            xTickOffset={16} yTickOffset={8}
          />
          {n > 0 && spec.series.filter((s) => s.mark === "bar").map((s) => (
            <ChartBars
              key={`bar-${s.key}`}
              plot={plot}
              points={pts.flatMap((p, i) => { const v = fin(s.accessor(p)); return v == null ? [] : [{ x: xAt(i), y: yAxis(s.axis)(v) }]; })}
              barWidth={s.barWidth ?? Math.max(4, (innerW / Math.max(1, n)) * 0.45)}
              radius={2}
              fill={s.color}
              opacity={opacityForKey(s.key)}
              activeIndex={activeIndex}
            />
          ))}
          {spec.area && n > 0 ? (() => {
            const ap = pts.map((p, i) => ({ x: xAt(i), y: fin(spec.area!.accessor(p)) })).filter((a) => a.y != null) as { x: number; y: number }[];
            if (ap.length < 2) return null;
            const scaled = ap.map((a) => ({ x: a.x, y: yAxis(spec.area!.axis)(a.y) }));
            const d = `M ${scaled.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L ")} L ${scaled[scaled.length - 1].x.toFixed(1)} ${innerH} L ${scaled[0].x.toFixed(1)} ${innerH} Z`;
            return <path d={d} transform={`translate(${plot.innerLeft}, ${plot.innerTop})`} fill={spec.area!.color} opacity={0.12} />;
          })() : null}
          {n > 0 && spec.series.filter((s) => s.mark !== "bar").map((s) => (
            <LinePath
              key={`line-${s.key}`}
              plot={plot}
              points={line(s)}
              stroke={s.color}
              strokeWidth={s.strokeWidth ?? 2}
              curve={s.mark === "step" ? "step" : s.mark === "step-after" ? "step-after" : "smooth"}
              strokeDasharray={s.mark === "line-dashed" ? "5 5" : undefined}
              markerRadius={s.markerRadius ?? (n <= 2 ? 3 : 0)}
              markerFill={s.color}
              opacity={opacityForKey(s.key)}
            />
          ))}
          {spec.dots && n > 0 ? (
            <g opacity={opacityForKey(spec.series.find((s) => s.axis === spec.dots!.axis)?.key ?? "")}>
              {pts.map((p, i) => { const v = fin(spec.dots!.accessor(p)); return spec.dots!.when(p) && v != null && (spec.dots!.axis === "left" ? L : R).finite
                ? <circle key={`dot-${i}`} cx={plot.innerLeft + xAt(i)} cy={plot.innerTop + yAxis(spec.dots!.axis)(v)} r={3.5} fill={spec.dots!.color} /> : null; })}
            </g>
          ) : null}
          {activeIndex != null && activeIndex < n ? (
            <line x1={plot.innerLeft + xAt(activeIndex)} x2={plot.innerLeft + xAt(activeIndex)} y1={plot.innerTop} y2={plot.innerTop + innerH} stroke={CHROME.axisText} strokeWidth={1} strokeDasharray="3 3" />
          ) : null}
          {n > 0 ? (
            <rect
              x={plot.innerLeft} y={plot.innerTop} width={innerW} height={innerH} fill="transparent"
              onMouseMove={(e) => {
                const box = e.currentTarget.getBoundingClientRect();
                const frac = (e.clientX - box.left) / Math.max(1, box.width);
                const i = spec.edgeToEdgeX ? Math.round(frac * (n - 1)) : Math.floor(frac * n);
                onActiveIndex(Math.max(0, Math.min(n - 1, i)));
              }}
              onMouseLeave={() => onActiveIndex(null)}
            />
          ) : null}
        </>
      )}
    </ChartFrame>
  );
}

function HoverTooltip({ spec, index }: { spec: ChartSpec; index: number }) {
  const pts = spec.points;
  const p = pts[index];
  if (p == null) return null;
  const n = pts.length;
  const marginLeft = spec.marginLeft ?? BASE_MARGIN.left;
  const frac = spec.edgeToEdgeX ? (n <= 1 ? 0.5 : index / (n - 1)) : (index + 0.5) / n;
  const flip = frac > 0.6;
  const left = `calc(${marginLeft}px + ${frac} * (100% - ${marginLeft + BASE_MARGIN.right}px))`;
  const tag = spec.tooltipTag ? spec.tooltipTag(p) : null;
  const rows = spec.tooltipRows(p);
  return (
    <div
      className="pointer-events-none absolute z-10 min-w-[170px] rounded-[8px] border px-3 py-2 shadow-sm"
      style={{ left, top: BASE_MARGIN.top + 4, transform: flip ? "translateX(calc(-100% - 10px))" : "translateX(10px)", background: SURFACES.card.bg, borderColor: SURFACES.card.border, fontFamily: FAM.plex }}
    >
      <div className="mb-1.5 flex items-center justify-between gap-3 border-b border-dashed pb-1.5" style={{ borderColor: SURFACES.divider.color }}>
        <span style={{ fontFamily: FAM.spaceMono, fontSize: 12, color: C.teal900 }}>{String(spec.labelOf(p) ?? "")}</span>
        {tag ? <span style={{ fontFamily: FAM.plex, fontSize: 10, fontWeight: 600, color: C.coral500 }}>{tag}</span> : null}
      </div>
      {rows.map((r) => (
        <div key={r.key} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5" style={{ fontSize: 11, color: C.sky600 }}>
            <span className="h-[3px] w-3 shrink-0" style={r.dashed ? { borderTop: `2px dashed ${r.color}` } : { background: r.color }} />
            {r.label}
          </span>
          <span style={{ fontFamily: FAM.spaceMono, fontSize: 12, fontWeight: 700, color: C.teal950 }}>{r.value}</span>
        </div>
      ))}
    </div>
  );
}

/** The full dual-axis chart card: header + optional KPI strip + chart (crosshair/tooltip) + legend rail + insight.
 *  Series colors ride the payload legend[].color (resolved by the caller); missing → the caller's DATA fallback. */
export function DualAxisChartCard({ title, picker, kpiStrip, spec, legend, opacityKeys, insight }: {
  title: string;
  picker: React.ReactNode;
  kpiStrip?: React.ReactNode;
  spec: ChartSpec;
  legend: any[];
  /** Legend rows already resolved to { key, label, value, unit, separator, swatch, color }. */
  opacityKeys: string[];
  insight: string;
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [focused, setFocused] = useState<Record<string, boolean>>({});
  const anyFocused = opacityKeys.some((k) => focused[k]);
  const opacityForKey = (k: string) => (anyFocused ? (focused[k] ? 1 : 0.2) : 1);
  const toggle = (k: string) => setFocused((prev) => ({ ...prev, [k]: !prev[k] }));
  const n = Array.isArray(spec.points) ? spec.points.length : 0;

  return (
    <Card className="h-full">
      <CardHeader title={title} action={picker} />
      <div className="mt-2 flex min-h-0 flex-1 gap-2">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {kpiStrip ? <div className="shrink-0">{kpiStrip}</div> : null}
          <div className="relative mt-1 min-h-0 flex-1" onMouseLeave={() => setActiveIndex(null)}>
            <ResponsiveSvg minWidth={220} minHeight={120}>
              {({ width, height }) => (
                <ChartSvg spec={spec} width={width} height={height} opacityForKey={opacityForKey} activeIndex={activeIndex} onActiveIndex={setActiveIndex} />
              )}
            </ResponsiveSvg>
            {activeIndex != null && activeIndex < n ? <HoverTooltip spec={spec} index={activeIndex} /> : null}
          </div>
        </div>
        <div className="flex w-[200px] shrink-0 flex-col gap-3 py-3 pl-3" style={{ borderLeft: `1px dashed ${SURFACES.divider.color}` }}>
          <div className="flex min-h-0 flex-1 flex-col gap-2 border-b border-dashed pb-3" style={{ borderColor: SURFACES.divider.color }}>
            {(Array.isArray(legend) ? legend : []).map((l, i) => {
              const key = String(l?.key ?? i);
              return (
                <InteractiveLegendRow
                  key={key}
                  color={l?.color || C.sky500}
                  label={String(l?.label ?? "")}
                  value={l?.value != null && l?.value !== "" ? String(l.value) : undefined}
                  unit={l?.unit || undefined}
                  separator={l?.separator || undefined}
                  swatch={l?.swatch || "square"}
                  swatchOpacity={1}
                  checked={focused[key] ?? false}
                  onToggle={() => toggle(key)}
                />
              );
            })}
          </div>
          {insight ? <AiSummary text={insight} className="shrink-0" /> : null}
        </div>
      </div>
    </Card>
  );
}
