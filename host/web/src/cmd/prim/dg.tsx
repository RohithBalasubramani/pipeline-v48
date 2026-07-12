// prim/dg.tsx — Diesel-Generator asset dashboard (cards 61,62,63,64,65,70,71,72,73) on PRIMITIVES ONLY.
// [primitives-only port — docs/primitives_inventory/PORT_CONTRACT.md + dg.md]
//
// Every card mounts CMD_V2 chart PRIMITIVES directly from its completed payload; header/legends/colors/values ride the
// payload. NO page-card imports (@cmd-v2/pages/**) — barrel only. The DG payloads are already component-props-shaped
// (one single-purpose key deep: liveOps / energyReliability / duty / snapshot+display / stats / chart), so each family
// renderer reads that key BY NAME and formats every scalar through fin()/fmtNum() so an honest-blank leaf renders '—',
// never NaN and never a crash. Series values for the engine/fuel timelines are DG-domain telemetry neuract does NOT
// carry (chart.series is empty in every real payload) — so those cards draw honest EMPTY timelines (real chrome, no
// fabricated points). Card 73 has no card_payloads seed → metadata-only (empty buckets + the demand-limit nameplate).
import React from "react";
import {
  AiSummary,
  BodyCard,
  buildChartDomain,
  Card,
  CardHeader,
  CHART_COLORS,
  ChartFrame,
  DataTable,
  DESCRIPTORS,
  EventDot,
  GridAxis,
  HorizontalBand,
  InteractiveLegendRow,
  KpiStatStrip,
  LinePath,
  PowerEnergyAnalysisPanel,
  PRESENTATION_LABELS,
  ProgressKpiCard,
  ResponsiveSvg,
  SamplingPicker,
  StackedBars,
  StatusBadge,
  UNITS,
  type KpiStatCell,
  type LegendSwatch,
  type SamplingSelection,
  type StatusTone,
} from "@cmd-v2/components/charts/primitives";
import { dash, fin, fmtNum } from "./shared";

// ── scalar/vocab helpers ──────────────────────────────────────────────────────────────────────────────────────────
/** Finitize→0 for chart bar heights / fractions where a blank reads as an empty (0) bar — never NaN. */
const zero = (v: any): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};
/** A KpiStatStrip value that stays honest: real number/string as-is, null/'' → '—'. */
const cellVal = (v: any): string | number => (v == null || v === "" ? "—" : v);
/** Payload KPI list → KpiStatStrip cells, generic (looked up by key, never a closed accessor record). */
const kpiCells = (list: any): KpiStatCell[] =>
  (Array.isArray(list) ? list : []).map((k: any, i: number) => ({
    id: String(k?.id ?? k?.label ?? i),
    label: String(k?.label ?? ""),
    value: cellVal(k?.value),
    unit: k?.unit || undefined,
    sub: k?.sub || undefined,
    swatch: k?.swatch || undefined,
    prefix: k?.prefix || undefined,
    valueColor: k?.valueColor || undefined,
    unitColor: k?.unitColor || undefined,
    subColor: k?.subColor || undefined,
  }));

// StatusBadge tone is a closed union; StatusBadge itself falls back to neutral, but keep an explicit safe map so an
// empty/garbage payload tone never reads as a valid one by accident.
const STATUS_TONES = new Set<StatusTone>(["fail", "critical", "warning", "success", "info", "neutral"]);
const toneOf = (t: any): StatusTone => (STATUS_TONES.has(String(t) as StatusTone) ? (String(t) as StatusTone) : "neutral");

// LiveOps service-bar segment color by the view's service tone (safe fallback → neutral). [dg.md §2.3]
const SERVICE_BAR_TONE: Record<string, string> = {
  success: CHART_COLORS.success500,
  warning: CHART_COLORS.warning500,
  fail: CHART_COLORS.destructive500,
  critical: CHART_COLORS.destructive500,
  info: CHART_COLORS.graphBlue600,
  neutral: CHART_COLORS.stone400,
};

// Valid legend swatch tokens — an unknown payload swatch degrades to 'square' (never a record-miss). [InteractiveLegendRow]
const SWATCHES = new Set<LegendSwatch>(["square", "line", "line-plain", "dot", "line-dashed", "line-markers", "square-filled"]);
const legendSwatch = (s: any): LegendSwatch => (SWATCHES.has(String(s) as LegendSwatch) ? (String(s) as LegendSwatch) : "square");

// Card 73 has NO card_payloads seed: the demand-limit nameplate line is a frontend const (mirrors CMD_V2 DG
// operations-runtime config.DEMAND_LIMIT_KW = 1700) so PowerEnergyAnalysisPanel can draw its axis over empty buckets.
const DEMAND_LIMIT_KW = 1700;

// ── card 70 / 72 — progress-KPI cards (ProgressKpiCard barrel) ────────────────────────────────────────────────────
function LiveOps({ p }: { p: any }) {
  const lo = p?.liveOps ?? {};
  const svc = lo.service ?? {};
  const st = lo.state ?? {};
  const ceil = fin(svc.ceiling);
  const avail = fin(svc.availability);
  const frac = fin(svc.fraction);
  const warn = fin(svc.warnPct);
  const usedPct = frac != null ? Math.round(frac * 100) : 0;
  const progress =
    frac != null
      ? {
          segments: [
            { id: "used", color: SERVICE_BAR_TONE[String(svc.tone)] ?? CHART_COLORS.stone400, weight: usedPct },
            { id: "remaining", color: CHART_COLORS.cream300, weight: Math.max(0, 100 - usedPct) },
          ],
          marker: warn != null ? { pct: warn } : null,
        }
      : undefined;
  return (
    <ProgressKpiCard
      title={String(lo.title ?? "")}
      headerAction={st.label ? <StatusBadge label={String(st.label)} tone={toneOf(st.tone)} /> : undefined}
      headline={{
        value: fmtNum(svc.hours, 0),
        target: ceil ?? undefined,
        unit: UNITS.hours,
        unitSuffix: DESCRIPTORS.toService,
        meta: avail != null ? `${PRESENTATION_LABELS.avail} ${fmtNum(avail, 1, UNITS.percent)}` : undefined,
      }}
      progress={progress}
      kpiStrips={[kpiCells(lo.topKpis), kpiCells(lo.stateKpis)]}
      insight={lo.insight || undefined}
    />
  );
}

function EnergyReliability({ p }: { p: any }) {
  const er = p?.energyReliability ?? {};
  const pf = fin(er.pf);
  const af = fin(er.activeFraction);
  const rf = fin(er.reactiveFraction);
  const progress =
    af != null || rf != null
      ? {
          segments: [
            { id: "active", color: CHART_COLORS.teal500, weight: Math.round((af ?? 0) * 100) },
            { id: "reactive", color: CHART_COLORS.graphRust600, weight: Math.round((rf ?? 0) * 100) },
          ],
        }
      : undefined;
  return (
    <ProgressKpiCard
      title={String(er.title ?? "")}
      headline={{
        value: fmtNum(er.apparentMvah, 1),
        unit: UNITS.energyMvah,
        meta: pf != null ? `${PRESENTATION_LABELS.pf} ${fmtNum(pf, 2)}` : undefined,
      }}
      progress={progress}
      kpiStrips={[kpiCells(er.cells)]}
      insight={er.insight || undefined}
    />
  );
}

// ── card 63 — Fuel Tank Anatomy: honest BodyCard note (the real card is a three.js Canvas — no barrel equivalent,
//    PORT_CONTRACT rule 1) surfacing the channel readouts + prose the payload carries. ───────────────────────────────
function FuelTank({ p }: { p: any }) {
  const snap = p?.snapshot ?? {};
  const disp = p?.display ?? {};
  const detail = disp.channelDetail ?? {};
  const cells: KpiStatCell[] = [
    { id: "level", label: "Level", value: fmtNum(snap.fuelLevel, 0, UNITS.percent), sub: detail.level || undefined, swatch: CHART_COLORS.teal500 },
    { id: "flow", label: "Flow", value: fmtNum(snap.fuelRate, 1, UNITS.fuelRate), sub: detail.flow || undefined, swatch: CHART_COLORS.sky500 },
    { id: "temp", label: "Temp", value: fmtNum(snap.fuelTemp, 0, UNITS.celsius), sub: detail.temperature || undefined, swatch: CHART_COLORS.mustard400 },
  ];
  return (
    <BodyCard title={String(disp.title ?? "Fuel Tank")}>
      <div className="flex h-full min-h-0 flex-col gap-2">
        <KpiStatStrip cells={cells} swatchShape="round" withCellDividers withBottomDivider={false} />
        {disp.subtitle ? <div style={{ fontSize: 12, opacity: 0.7 }}>{String(disp.subtitle)}</div> : null}
        {disp.aiText ? <AiSummary text={String(disp.aiText)} density="compact" /> : null}
        <div className="mt-auto" style={{ fontSize: 11, color: CHART_COLORS.sky400 }}>
          3D tank anatomy view is not available in this render — channel readouts shown above.
        </div>
      </div>
    </BodyCard>
  );
}

// ── card 64 — All Runs / Fuel Log: stats header + DataTable (columns from stats.columnLabels; run rows honest-empty). ─
// Column id → row field + formatting (DATA alias map; the payload's columnLabels own the header WORDS, accessors fixed).
const RUN_COLS_64: Array<{ key: string; field: string; dec?: number; unit?: string; start?: boolean; align?: "left" | "right" }> = [
  { key: "start", field: "clock", start: true, align: "left" },
  { key: "dur", field: "duration", dec: 2, unit: UNITS.hours, align: "right" },
  { key: "load", field: "loadAvg", dec: 0, unit: UNITS.percent, align: "right" },
  { key: "fuel", field: "fuelL", dec: 1, unit: UNITS.litre, align: "right" },
  { key: "kwh", field: "kWh", dec: 1, align: "right" },
  { key: "sfc", field: "sfc", dec: 2, align: "right" },
];

function RunsLog({ p }: { p: any }) {
  const s = p?.stats ?? {};
  const labels = s.columnLabels ?? {};
  const rows = Array.isArray(p?.runs) ? p.runs : Array.isArray(s.runs) ? s.runs : [];
  const columns = RUN_COLS_64.map((c) => ({
    id: c.key,
    header: String(labels[c.key] ?? c.key),
    align: c.align,
    render: (row: any) => (c.start ? dash(row?.[c.field]) : c.dec != null ? fmtNum(row?.[c.field], c.dec, c.unit) : dash(row?.[c.field])),
  }));
  const mwh = fin(s.totalKwh) != null ? (fin(s.totalKwh) as number) / 1000 : null;
  const sub = [
    `${fmtNum(s.avgLoad, 0, UNITS.percent)} avg`,
    fmtNum(s.runHours, 1, UNITS.hours),
    fmtNum(s.totalFuelL, 1, UNITS.litre),
    fmtNum(mwh, 1, UNITS.energyMwh),
  ].join(" · ");
  const starts = fin(s.starts);
  return (
    <BodyCard title={String(s.title ?? "")}>
      <div className="flex h-full min-h-0 flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <span style={{ fontSize: 12, color: CHART_COLORS.sky400 }}>{sub}</span>
          <span style={{ fontSize: 11, fontWeight: 600, color: CHART_COLORS.teal700 }}>
            {starts != null ? `${starts} starts` : dash(null)}
          </span>
        </div>
        <div className="min-h-0 flex-1">
          <DataTable
            columns={columns}
            rows={rows}
            getRowKey={(row: any, i: number) => String(row?.id ?? i)}
            ariaLabel="Fuel runs"
            emptyState="No runs in this period"
            fillHeight
            scrollBody
            stickyHeader
          />
        </div>
      </div>
    </BodyCard>
  );
}

// ── cards 61 / 62 / 65 — composite chrome-over-timeline (KpiStatStrip + SVG timeline + legend rail + AiSummary). ─────
// The plotted VALUES for engine/fuel telemetry are absent from neuract, so chart.series is empty on every real payload
// → an honest EMPTY timeline. The renderer still plots series[].values IF a payload ever carries them (generic, by key).
function TimelineSvg({ chart }: { chart: any }) {
  const axes = Array.isArray(chart?.axes) ? chart.axes : [];
  const series = Array.isArray(chart?.series) ? chart.series : [];
  const band = chart?.band ?? {};
  const events = Array.isArray(chart?.events) ? chart.events : [];
  const leftAxis = axes.find((a: any) => a?.orientation !== "right") ?? axes[0] ?? {};
  const axisDomain = Array.isArray(leftAxis.domain) ? leftAxis.domain.map(fin).filter((v: any) => v != null) : [];
  const seriesVals: number[] = series.flatMap((s: any) =>
    (Array.isArray(s?.values) ? s.values : []).map(fin).filter((v: any) => v != null),
  );
  const bandVals = [fin(band.y1), fin(band.y2)].filter((v) => v != null) as number[];
  const dom = buildChartDomain({
    values: seriesVals.length ? seriesVals : [],
    references: [...axisDomain, ...bandVals],
    padRatio: 0.08,
    integerTicks: false,
  });
  const maxLen = series.reduce((m: number, s: any) => Math.max(m, Array.isArray(s?.values) ? s.values.length : 0), 0);
  return (
    <ResponsiveSvg minHeight={120}>
      {({ width, height }) => (
        <ChartFrame width={width} height={height} margin={{ top: 16, right: 20, bottom: 26, left: 46 }}>
          {(plot) => {
            const { innerWidth, innerHeight } = plot;
            const span = dom.maxY - dom.minY || 1;
            const yScale = (v: number) => innerHeight - ((v - dom.minY) / span) * innerHeight;
            const xFor = (i: number) => (maxLen > 1 ? (i / (maxLen - 1)) * innerWidth : innerWidth / 2);
            const yTicks = dom.yTicks.map((v) => ({ y: yScale(v), label: fmtNum(v, Math.abs(v) >= 100 ? 0 : 1) }));
            const y1 = fin(band.y1);
            const y2 = fin(band.y2);
            return (
              <>
                <GridAxis plot={plot} yTicks={yTicks} showHorizontalGrid showXAxisLine showYAxisLine labelColor={CHART_COLORS.sky400} />
                {y1 != null && y2 != null ? (
                  <HorizontalBand plot={plot} yTop={yScale(Math.max(y1, y2))} yBottom={yScale(Math.min(y1, y2))} fill={CHART_COLORS.sage100} opacity={0.6} />
                ) : null}
                {series.map((s: any, si: number) => {
                  const pts = (Array.isArray(s?.values) ? s.values : []).map((v: any, i: number) => {
                    const n = fin(v);
                    return { x: xFor(i), y: n == null ? null : yScale(n) };
                  });
                  return pts.length ? <LinePath key={si} plot={plot} points={pts} stroke={s?.color ?? CHART_COLORS.teal500} strokeWidth={2} curve="smooth" /> : null;
                })}
                {events.map((e: any, ei: number) => {
                  const v = fin(e?.value);
                  const idx = fin(e?.idx);
                  return v != null && idx != null ? (
                    <EventDot key={ei} plot={plot} x={xFor(idx)} y={yScale(v)} color={e?.severity === "danger" ? CHART_COLORS.coral500 : CHART_COLORS.mustard400} />
                  ) : null;
                })}
              </>
            );
          }}
        </ChartFrame>
      )}
    </ResponsiveSvg>
  );
}

function CompositeChart({ p }: { p: any }) {
  const chart = p?.chart ?? {};
  const legend = Array.isArray(chart.legend) ? chart.legend : [];
  return (
    <Card className="h-full" overflow="hidden">
      <CardHeader title={String(chart.title ?? "")} />
      <div className="flex min-h-0 flex-1 gap-3 pt-2">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <KpiStatStrip cells={kpiCells(chart.kpis)} withCellDividers withBottomDivider />
          <div className="min-h-0 flex-1 p-2 pt-3">
            <TimelineSvg chart={chart} />
          </div>
        </div>
        <aside className="flex w-[200px] shrink-0 flex-col gap-3 overflow-hidden border-l pl-3 pt-2" style={{ borderColor: CHART_COLORS.cream200 }}>
          <div className="flex flex-col gap-1">
            {legend.map((l: any, i: number) => (
              <InteractiveLegendRow
                key={i}
                color={l?.color ?? CHART_COLORS.teal500}
                label={String(l?.label ?? "")}
                value={l?.value != null ? String(l.value) : undefined}
                unit={l?.unit || undefined}
                swatch={legendSwatch(l?.swatch)}
                checked={false}
                onToggle={() => undefined}
              />
            ))}
          </div>
          {chart.insight ? (
            <div className="mt-auto border-t pt-2" style={{ borderColor: CHART_COLORS.cream200, borderStyle: "dashed" }}>
              <AiSummary text={String(chart.insight)} density="compact" />
            </div>
          ) : null}
        </aside>
      </div>
    </Card>
  );
}

// ── card 71 — Runtime & Duty: KpiStatStrip + dual-axis (bars run-h / line load%) + runs DataTable rail. ──────────────
// SamplingPicker committed selection → host date_window (mirrors fill/dg-operations-runtime/date-wiring.ts). A function
// can't ride a JSON payload, so the picker state lives here and Apply fires onDateChange with the translated window.
function samplingToWindow(sel: any): any {
  const start = sel?.range?.start;
  const end = sel?.range?.end;
  const res = (d: string) => (sel?.resolution === "daily" ? "day" : sel?.resolution === "shift" ? "shift" : sel?.resolution === "hourly" ? "hourly" : d);
  switch (sel?.preset) {
    case "yesterday": return { range: "yesterday", sampling: res("2hour") };
    case "last-7-days": return { range: "last-7-days", sampling: res("day") };
    case "this-month": return { range: "this-month", sampling: res("day") };
    case "last-month": return { range: "custom-range", sampling: res("week"), start, end };
    case "custom": return { range: "custom-range", sampling: res("hourly"), start, end };
    default: return { range: "today", sampling: res("hourly") };
  }
}

const RUN_COLS_71: Array<{ key: string; field: string; dec?: number; unit?: string; start?: boolean; align?: "left" | "right" }> = [
  { key: "start", field: "clock", start: true, align: "left" },
  { key: "dur", field: "duration", dec: 2, unit: UNITS.hours, align: "right" },
  { key: "load", field: "loadAvg", dec: 0, unit: UNITS.percent, align: "right" },
];

function DutyChart({ duty, selected, onSelect }: { duty: any; selected: number | null; onSelect: (i: number | null) => void }) {
  const points = Array.isArray(duty?.points) ? duty.points : [];
  const hDom = buildChartDomain({ values: points.map((p: any) => zero(p?.runHours)), references: [0], padRatio: 0.1, integerTicks: false });
  const PCT_MAX = 100;
  const interval = Math.max(1, fin(duty?.tickInterval) ?? 1);
  return (
    <div className="min-h-0 min-w-0 flex-1 p-2 pt-3">
      <ResponsiveSvg minHeight={120}>
        {({ width, height }) => (
          <ChartFrame width={width} height={height} margin={{ top: 16, right: 44, bottom: 30, left: 52 }}>
            {(plot) => {
              const { innerWidth, innerHeight } = plot;
              const slot = points.length > 0 ? innerWidth / points.length : 0;
              const xFor = (i: number) => (i + 0.5) * slot;
              const hScale = (v: number) => (hDom.maxY === 0 ? 0 : (v / hDom.maxY) * innerHeight);
              const pctScale = (v: number) => (v / PCT_MAX) * innerHeight;
              const xTicks = points
                .map((p: any, i: number) => ({ x: xFor(i), label: i % interval === 0 ? String(p?.label ?? "") : "" }))
                .filter((t: any) => t.label !== "");
              const yTicksH = hDom.yTicks.map((v) => ({ y: innerHeight - hScale(v), label: fmtNum(v, 2) }));
              const yTicksP = [0, 25, 50, 75, 100].map((v) => ({ y: innerHeight - pctScale(v), label: String(v) }));
              const bars = points.map((p: any, i: number) => ({
                id: `${i}`,
                x: xFor(i),
                segments: [{ height: hScale(zero(p?.runHours)), color: selected != null && i !== selected ? CHART_COLORS.cream300 : CHART_COLORS.teal500, topRadius: 2 }],
              }));
              const linePts = points.map((p: any, i: number) => {
                const lp = fin(p?.loadPct);
                return { x: xFor(i), y: lp == null ? null : innerHeight - pctScale(lp) };
              });
              const HIT = Math.max(24, slot);
              return (
                <>
                  <GridAxis
                    plot={plot}
                    xTicks={xTicks}
                    yTicks={yTicksH}
                    rightYTicks={yTicksP}
                    showHorizontalGrid
                    showXAxisLine
                    showYAxisLine
                    showRightYAxisLine
                    yAxisLabel="Run h"
                    rightYAxisLabel="%"
                    yAxisTitleOffset={36}
                    rightYAxisTitleOffset={32}
                    labelColor={CHART_COLORS.sky400}
                  />
                  <StackedBars plot={plot} bars={bars} barWidth={18} />
                  <LinePath plot={plot} points={linePts} stroke={CHART_COLORS.teal300} strokeWidth={2} curve="smooth" />
                  {points.map((_: any, i: number) => (
                    <rect
                      key={`hit-${i}`}
                      x={plot.innerLeft + xFor(i) - HIT / 2}
                      y={plot.innerTop}
                      width={HIT}
                      height={innerHeight}
                      fill="transparent"
                      style={{ cursor: "pointer" }}
                      onClick={() => onSelect(selected === i ? null : i)}
                    />
                  ))}
                </>
              );
            }}
          </ChartFrame>
        )}
      </ResponsiveSvg>
    </div>
  );
}

function RuntimeDuty({ p, onDateChange }: { p: any; onDateChange?: (dw: any) => void }) {
  const duty = p?.duty ?? {};
  const runs = p?.runs && typeof p.runs === "object" ? p.runs : {};
  const runRows = Array.isArray(runs.rows) ? runs.rows : [];
  const runLabels = runs.columnLabels ?? {};
  const [sampling, setSampling] = React.useState<SamplingSelection>({ preset: "today", range: null });
  const [selected, setSelected] = React.useState<number | null>(null);
  const points = Array.isArray(duty.points) ? duty.points : [];
  const safeSel = points.length > 0 ? selected : null;
  const columns = RUN_COLS_71.map((c) => ({
    id: c.key,
    header: String(runLabels[c.key] ?? (c.key === "start" ? "Start" : c.key === "dur" ? "Dur" : "Load")),
    align: c.align,
    render: (row: any) => (c.start ? dash(row?.[c.field]) : fmtNum(row?.[c.field], c.dec, c.unit)),
  }));
  return (
    <Card className="h-full" overflow="hidden">
      <CardHeader
        title={String(duty.title ?? "")}
        action={
          <SamplingPicker
            value={sampling}
            onChange={(next) => {
              setSampling(next);
              setSelected(null);
              try {
                onDateChange?.(samplingToWindow(next));
              } catch {
                /* window stays */
              }
            }}
            align="end"
          />
        }
      />
      <div className="grid min-h-0 flex-1" style={{ gridTemplateColumns: "minmax(0, 1fr) 235px" }}>
        <div className="flex min-h-0 min-w-0 flex-col">
          <KpiStatStrip cells={kpiCells(duty.topKpis)} withCellDividers withBottomDivider />
          <DutyChart duty={duty} selected={safeSel} onSelect={setSelected} />
        </div>
        <div className="flex min-h-0 flex-col overflow-hidden pl-3">
          <div className="flex shrink-0 items-center justify-between gap-2 border-b pb-[10px]" style={{ borderColor: CHART_COLORS.cream300 }}>
            <p className="truncate text-[14px]" style={{ color: CHART_COLORS.teal900 }}>
              {String(runs.headerLabel ?? "All runs")}
            </p>
            <span style={{ fontSize: 11, fontWeight: 600, color: CHART_COLORS.teal700 }}>{`${runRows.length} STARTS`}</span>
          </div>
          <div className="min-h-0 flex-1">
            <DataTable
              columns={columns}
              rows={runRows}
              getRowKey={(row: any, i: number) => String(row?.id ?? i)}
              ariaLabel="Run events"
              emptyState="No runs in this period"
              fillHeight
              scrollBody
              stickyHeader
              headerHeight={26}
              rowHeight={42}
            />
          </div>
        </div>
      </div>
    </Card>
  );
}

// ── card 73 — Power Energy Analysis: PowerEnergyAnalysisPanel is ITSELF a barrel primitive → mount directly. ─────────
// No card_payloads seed → buckets empty + the demand-limit nameplate; the panel computes KPIs/insight in-component.
function PowerEnergy({ p, onDateChange }: { p: any; onDateChange?: (dw: any) => void }) {
  const buckets = (Array.isArray(p?.buckets) ? p.buckets : [])
    .filter((b: any) => b && typeof b === "object")
    .map((b: any) => ({ label: String(b.label ?? ""), demand: zero(b.demand), active: zero(b.active), reactive: zero(b.reactive) }));
  const limitKw = fin(p?.limitKw) ?? DEMAND_LIMIT_KW;
  const [sampling, setSampling] = React.useState<SamplingSelection>({ preset: "today", range: null });
  const [selIdx, setSelIdx] = React.useState<number | null>(null);
  return (
    <PowerEnergyAnalysisPanel
      buckets={buckets}
      selIdx={buckets.length > 0 ? selIdx : null}
      limitKw={limitKw}
      sampling={sampling}
      onSamplingChange={(next) => {
        setSampling(next);
        setSelIdx(null);
        try {
          onDateChange?.(samplingToWindow(next));
        } catch {
          /* window stays */
        }
      }}
    />
  );
}

export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  61: (p) => <CompositeChart p={p} />,
  62: (p) => <CompositeChart p={p} />,
  63: (p) => <FuelTank p={p} />,
  64: (p) => <RunsLog p={p} />,
  65: (p) => <CompositeChart p={p} />,
  70: (p) => <LiveOps p={p} />,
  71: (p, onDateChange) => <RuntimeDuty p={p} onDateChange={onDateChange} />,
  72: (p) => <EnergyReliability p={p} />,
  73: (p, onDateChange) => <PowerEnergy p={p} onDateChange={onDateChange} />,
};
