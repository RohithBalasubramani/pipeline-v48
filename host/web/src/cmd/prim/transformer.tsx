// prim/transformer.tsx — TRANSFORMER asset-dashboard family (cards 74–81) on PRIMITIVES ONLY. [primitives-only port]
//
// Every card mounts CMD_V2 chart primitives directly from its completed payload slice ({ variant, <slice>: <slice> });
// header/status/legends/colors/values all ride the payload (AI-morphable). The four chart cards (76/77/79/81) share the
// generic dual-axis shell in ./transformer-charts (ChartFrame+GridAxis+ChartBars/LinePath/Band/ReferenceLine + sidebar
// legend + AiSummary + SamplingPicker wired to onDateChange); the four snapshot cards (74/75/78/80) mount FillBar /
// SegmentedArcGauge / DataTable directly. HONESTY: every scalar rides fin()/dash() → a blank leaf renders '—' or an
// empty-chrome chart (axes only), NEVER a synthetic bucket, NEVER a record-miss crash (tone lookups fall back).
//   74 Thermal Life · 75 Life & Capacity · 76 Thermal Timeline · 77 Insulation Aging
//   78 Tap Position · 79 Voltage Regulation · 80 Recent Tap Changes · 81 Tap Activity
import React, { useState } from "react";
import {
  AiSummary,
  Card,
  CardBodySkeleton,
  CardHeader,
  CHART_COLORS as C,
  DataTable,
  FillBar,
  KpiStatStrip,
  ListBodySkeleton,
  PRESENTATION_LABELS,
  SamplingPicker,
  SegmentedArcGauge,
  StatusPill,
  SURFACES,
  TYPOGRAPHY_FAMILY as FAM,
} from "@cmd-v2/components/charts/primitives";
import { dash, fin, fmtNum } from "./shared";
import { DualAxisChartCard, type ChartSpec, type Series } from "./transformer-charts";

type OnDateChange = (dw: any) => void;

// ── safe lookups ─────────────────────────────────────────────────────────────────────────────────────────────────
const TONES = new Set(["normal", "alarm", "watch", "info"]);
/** StatusPill/KpiStatStrip crash on an unknown tone (record-miss on STATUS_PILL_TONES / KPI_STATUS_DOT_PRESETS).
 *  An empty/unknown tone (honest-blank status) falls back to 'info' (neutral), never a record miss. */
const safeTone = (t: any): "normal" | "alarm" | "watch" | "info" => (TONES.has(String(t)) ? String(t) as any : "info");
const fx = (v: any, d: number): string => { const n = fin(v); return n == null ? "—" : n.toFixed(d); };
/** Plot color for a series key: the payload legend row's color wins (AI-morphable), else the family DATA fallback. */
const colorFor = (legend: any[], fallback: Record<string, string>) => (key: string): string => {
  const row = (Array.isArray(legend) ? legend : []).find((l) => String(l?.key) === key);
  return row?.color || fallback[key] || C.sky500;
};

// ── series DATA fallbacks + per-card key→mark/axis/accessor maps (payload legend picks WHICH keys render) ─────────
const TIMELINE_COLORS: Record<string, string> = { load: C.peach400, hotspot: C.coral400, oil: C.sky500, efficiency: C.sage500 };
const AGING_COLORS: Record<string, string> = { lol: C.mustard500, faa: C.lavender400 };
const REG_COLORS: Record<string, string> = { voltage: C.sky300, tap: C.graphite400 };
const ACTIVITY_COLORS: Record<string, string> = { today: C.lavender400, total: C.graphite400 };

interface KeyDesc { mark: Series["mark"]; axis: "left" | "right"; get: (p: any) => number | null; barWidth?: number; markerRadius?: number; strokeWidth?: number }
const TIMELINE_KEYS: Record<string, KeyDesc> = {
  load: { mark: "bar", axis: "right", get: (p) => p?.loadPct, barWidth: 12 },
  hotspot: { mark: "line", axis: "left", get: (p) => p?.hotspotC, markerRadius: 4 },
  oil: { mark: "line", axis: "left", get: (p) => p?.oilC, markerRadius: 4 },
  efficiency: { mark: "line-dashed", axis: "right", get: (p) => p?.efficiencyPct, markerRadius: 4 },
};
const AGING_KEYS: Record<string, KeyDesc> = {
  lol: { mark: "line", axis: "left", get: (p) => p?.lolPct },
  faa: { mark: "bar", axis: "right", get: (p) => p?.faa },
};
const REG_KEYS: Record<string, KeyDesc> = {
  voltage: { mark: "line", axis: "left", get: (p) => p?.voltageKv },
  tap: { mark: "step", axis: "right", get: (p) => p?.tap },
};
const ACTIVITY_KEYS: Record<string, KeyDesc> = {
  today: { mark: "bar", axis: "left", get: (p) => p?.count, barWidth: 8 },
  total: { mark: "step-after", axis: "right", get: (p) => p?.cumTotal, strokeWidth: 1.5 },
};

/** Build the series[] for a chart from the legend keys the payload declares (∩ the card's key map). */
function seriesFrom(legend: any[], keys: Record<string, KeyDesc>, color: (k: string) => string): Series[] {
  return (Array.isArray(legend) ? legend : []).flatMap((l) => {
    const key = String(l?.key ?? "");
    const d = keys[key];
    return d ? [{ key, accessor: d.get, mark: d.mark, axis: d.axis, color: color(key), barWidth: d.barWidth, markerRadius: d.markerRadius, strokeWidth: d.strokeWidth }] : [];
  });
}

// ── SamplingPicker DATA (presets/resolutions reproduced from the CMD_V2 tab configs) + onDateChange mapping ───────
const P = (value: string, label: string) => ({ value, label });
const TIMELINE_PRESETS = [P("today", "Today"), P("yesterday", "Yesterday")];
const TIMELINE_RES = [P("3-hourly", "3-Hourly"), P("hourly", "Hourly")];
const AGING_PRESETS = [P("today", "Today"), P("yesterday", "Yesterday"), P("last-7-days", "Last 7 days"), P("this-month", "This month"), P("last-month", "Last month")];
const AGING_RES = [P("daily", "Daily"), P("weekly", "Weekly")];
const TAP_PRESETS = [...AGING_PRESETS, P("custom", "Custom range")];
const TAP_RES = [P("hourly", "Hourly"), P("shift", "By shift")];
const TAP_SHIFT = [P("all", "All shifts"), P("a", "Shift A"), P("b", "Shift B"), P("c", "Shift C")];

/** SamplingPicker preset → host DateWindow.range (reimplements the retired fill's reqToDateWindow RANGE map). */
const PRESET_TO_RANGE: Record<string, string> = {
  today: "today", yesterday: "yesterday", "last-7-days": "last-7-days",
  "this-month": "this-month", "last-month": "last-month", custom: "custom-range",
};
// Card 76 (timeline): 3-Hourly → `hourly` (3-hour bucket), Hourly → `hour` (1-hour bucket). [timelineSelectionToReq]
const timelineToDW = (s: any) => ({ range: PRESET_TO_RANGE[s?.preset] ?? "today", sampling: s?.resolution === "hourly" ? "hour" : "hourly" });
// Card 77 (aging): Daily → `day`, Weekly → `week`. [agingSelectionToReq]
const agingToDW = (s: any) => ({ range: PRESET_TO_RANGE[s?.preset] ?? "this-month", sampling: s?.resolution === "weekly" ? "week" : "day" });
// Cards 79/81 (tap): sub-day ranges take Hourly/By-shift; multi-day ranges coarsen (7d → day, month → week). [tapSelectionToReq]
const tapToDW = (s: any) => {
  const range = PRESET_TO_RANGE[s?.preset] ?? "today";
  const subDay = range === "today" || range === "yesterday" || range === "custom-range";
  if (subDay) return { range, sampling: s?.resolution === "shift" ? "shift" : "hourly" };
  return { range, sampling: range === "last-7-days" ? "day" : "week" };
};

/** Self-contained SamplingPicker: owns its committed selection, forwards each Apply to onDateChange (guarded). */
function Picker({ initial, presets, resolutionOptions, shiftOptions, shiftWhenResolution, toDW, onDateChange }: {
  initial: any; presets: any[]; resolutionOptions: any[]; shiftOptions?: any[]; shiftWhenResolution?: string;
  toDW: (s: any) => any; onDateChange?: OnDateChange;
}) {
  const [sel, setSel] = useState<any>(initial);
  return (
    <SamplingPicker
      value={sel}
      onChange={(next: any) => { setSel(next); try { onDateChange && onDateChange(toDW(next)); } catch { /* keep selection */ } }}
      presets={presets as any}
      resolutionOptions={resolutionOptions as any}
      shiftOptions={shiftOptions as any}
      shiftWhenResolution={shiftWhenResolution}
      align="end"
    />
  );
}

// ── card 74 — Thermal Life: stress FillBar + winding/oil metric strip + AiSummary ────────────────────────────────
function Card74({ p }: { p: any }) {
  const s = p?.thermalLife ?? {};
  const status = s.status ?? {};
  const metrics = Array.isArray(s.metrics) ? s.metrics : [];
  const stressPct = fin(s.stressPct);
  const borderPct = fin(s.stressBorderPct);
  const action = status.label ? <StatusPill label={String(status.label)} tone={safeTone(status.tone)} /> : undefined;
  return (
    <Card className="h-full" style={{ paddingLeft: 24, paddingRight: 24 }}>
      <CardHeader title={dash(s.title)} action={action} />
      {p?.loading === true ? (
        <CardBodySkeleton kpiCells={metrics.length || 3} className="mt-4" />
      ) : (
        <>
          <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3">
            <div className="flex items-baseline gap-1.5">
              <span className="flex items-baseline gap-0.5">
                <span style={{ fontFamily: FAM.spaceMono, fontSize: 24, fontWeight: 700, color: C.teal990, letterSpacing: "-0.26px" }}>{dash(s.stressPct)}</span>
                <span style={{ fontFamily: FAM.plex, fontSize: 12, color: C.teal800 }}>%</span>
                <span style={{ fontFamily: FAM.spaceMono, fontSize: 16, fontWeight: 700, color: C.sky600 }}>/100</span>
              </span>
              <span style={{ fontFamily: FAM.plex, fontSize: 13, color: C.sky600 }}>{PRESENTATION_LABELS.thermalStress}</span>
            </div>
            <div>
              <FillBar pct={stressPct ?? 0} trackColor={C.cream200} fillColor={C.teal400} fillAboveMarker={C.coral500} marker={borderPct != null ? { pct: borderPct, color: C.teal900 } : null} height={32} />
              <div className="mt-1.5 flex items-center justify-between" style={{ fontFamily: FAM.spaceMono, fontSize: 12, color: C.sky400 }}>
                <span>0</span>
                <span>{dash(s.stressBorderLabel)}<span style={{ color: C.teal900 }}>{borderPct != null ? `${borderPct}%` : "—"}</span></span>
                <span>100%</span>
              </div>
            </div>
          </div>
          <div className="shrink-0">
            <div className="border-t border-dashed" style={{ borderColor: SURFACES.divider.color }}>
              <KpiStatStrip
                cells={metrics.map((m: any, i: number) => ({
                  id: String(m?.label ?? i),
                  label: String(m?.label ?? ""),
                  value: m?.value != null && m?.value !== "" ? String(m.value) : "—",
                  unit: m?.unit || undefined,
                  status: m?.statusLabel ? { label: String(m.statusLabel), tone: safeTone(m.tone) } : undefined,
                }))}
                height="auto"
                flushEnds
                withBottomDivider={false}
              />
            </div>
            {s.insight ? (
              <div className="border-t border-dashed pt-3" style={{ borderColor: SURFACES.divider.color }}>
                <AiSummary text={String(s.insight)} density="compact" />
              </div>
            ) : null}
          </div>
        </>
      )}
    </Card>
  );
}

// ── card 75 — Life & Capacity: two FillBar groups ────────────────────────────────────────────────────────────────
function BarGroup({ value, denom, label, pct, fill, caption }: { value: string; denom: string; label: string; pct: number; fill: string; caption: string }) {
  return (
    <div className="flex flex-col">
      <div className="flex items-baseline gap-1.5">
        <span className="flex items-baseline gap-0.5">
          <span style={{ fontFamily: FAM.spaceMono, fontSize: 24, fontWeight: 700, color: C.teal990, letterSpacing: "-0.26px" }}>{value}</span>
          <span style={{ fontFamily: FAM.spaceMono, fontSize: 16, fontWeight: 700, color: C.sky600 }}>{denom}</span>
        </span>
        <span style={{ fontFamily: FAM.plex, fontSize: 13, color: C.sky600 }}>{label}</span>
      </div>
      <div className="mt-2"><FillBar pct={pct} trackColor={C.cream200} fillColor={fill} height={32} /></div>
      {caption ? <span className="mt-1.5" style={{ fontFamily: FAM.spaceMono, fontSize: 12, color: C.sky400 }}>{caption}</span> : null}
    </div>
  );
}
function Card75({ p }: { p: any }) {
  const s = p?.lifeCapacity ?? {};
  const status = s.status ?? {};
  const action = status.label ? <StatusPill label={String(status.label)} tone={safeTone(status.tone)} /> : undefined;
  const years = fin(s.lifeRemainingYears);
  return (
    <Card className="h-full" style={{ paddingLeft: 24, paddingRight: 24 }}>
      <CardHeader title={dash(s.title)} action={action} />
      {p?.loading === true ? (
        <ListBodySkeleton rows={2} className="mt-3" />
      ) : (
        <div className="mt-3 flex min-h-0 flex-1 flex-col justify-between gap-3">
          <BarGroup
            value={years != null ? years.toFixed(1) : "—"}
            denom={`/${dash(s.lifeBaseYears)}${s.lifeRemainingUnit || ""}`}
            label={dash(s.lifeRemainingLabel)}
            pct={fin(s.lifeFillPct) ?? 0}
            fill={C.mustard500}
            caption={String(s.agingCaption ?? "")}
          />
          <div className="border-t border-dashed" style={{ borderColor: SURFACES.divider.color }} />
          <BarGroup
            value={fin(s.deratedLoadKva) != null ? fmtNum(s.deratedLoadKva, 0) : "—"}
            denom={`/${dash(s.deratedKva)}${s.deratedUnit || ""}`}
            label={dash(s.deratedLabel)}
            pct={fin(s.deratedFillPct) ?? 0}
            fill={C.sage500}
            caption={String(s.headroomCaption ?? "")}
          />
        </div>
      )}
    </Card>
  );
}

// ── card 78 — Tap Position: SegmentedArcGauge + KPI strip + AiSummary ─────────────────────────────────────────────
const GAUGE = { segment: C.lavender500, label: C.graphite50, needle: C.graphite600, optimal: C.sage500 };
function Card78({ p }: { p: any }) {
  const s = p?.tapPosition ?? {};
  const status = s.status ?? {};
  const gauge = s.gauge ?? {};
  const count = fin(gauge.count);
  const kpis = Array.isArray(s.kpis) ? s.kpis : [];
  const action = status.label ? <StatusPill label={String(status.label)} tone={safeTone(status.tone)} /> : undefined;
  return (
    <Card className="h-full" style={{ paddingLeft: 24, paddingRight: 24 }}>
      <CardHeader title={dash(s.title)} action={action} />
      {p?.loading === true ? (
        <CardBodySkeleton kpiCells={kpis.length || 3} className="mt-2" />
      ) : (
        <>
          <div className="flex min-h-0 flex-1 items-center justify-center py-2">
            {count != null && count > 0 ? (
              <div className="aspect-[200/114] max-h-full w-full max-w-[200px]">
                <SegmentedArcGauge count={count} value={fin(gauge.value) ?? 1} optimal={fin(gauge.optimal)} segmentFill={GAUGE.segment} labelColor={GAUGE.label} needleColor={GAUGE.needle} optimalColor={GAUGE.optimal} />
              </div>
            ) : (
              <span style={{ fontFamily: FAM.spaceMono, fontSize: 20, color: C.sky400 }}>—</span>
            )}
          </div>
          <div className="shrink-0">
            <div className="border-t border-dashed" style={{ borderColor: SURFACES.divider.color }}>
              <KpiStatStrip
                cells={kpis.map((k: any, i: number) => ({ id: String(k?.id ?? i), label: String(k?.label ?? ""), value: k?.value != null && k?.value !== "" ? String(k.value) : "—", valueColor: k?.valueColor || undefined }))}
                height="auto"
                flushEnds
                withBottomDivider={false}
              />
            </div>
            {s.insight ? (
              <div className="border-t border-dashed pt-3" style={{ borderColor: SURFACES.divider.color }}>
                <AiSummary text={String(s.insight)} density="compact" />
              </div>
            ) : null}
          </div>
        </>
      )}
    </Card>
  );
}

// ── card 80 — Recent Tap Changes: DataTable (headers ride the payload's columnLabels) ─────────────────────────────
function Card80({ p }: { p: any }) {
  const s = p?.changes ?? {};
  const labels = s.columnLabels ?? {};
  const rows = Array.isArray(s.rows) ? s.rows : [];
  const columns = [
    { id: "time", header: String(labels.time ?? "Time"), render: (r: any) => dash(r?.time), fit: true, fitMin: 76, fitMax: 110 },
    { id: "from", header: <span className="block text-center">{String(labels.from ?? "From")}</span>, render: (r: any) => <span className="block text-center">{dash(r?.fromTap)}</span> },
    { id: "to", header: <span className="block text-center">{String(labels.to ?? "To")}</span>, render: (r: any) => <span className="block text-center">{dash(r?.toTap)}</span> },
  ];
  return (
    <Card className="h-full" style={{ paddingLeft: 24, paddingRight: 24 }}>
      <CardHeader title={dash(s.title)} />
      {p?.loading === true ? (
        <ListBodySkeleton rows={6} className="mt-2" />
      ) : (
        <div className="mt-2 min-h-0 flex-1">
          <DataTable columns={columns as any} rows={rows} getRowKey={(r: any, i: number) => `${r?.time ?? ""}-${i}`} ariaLabel="Recent tap changes" headerHeight={32} rowHeight={32} scrollBody emptyState="No tap changes today" />
        </div>
      )}
    </Card>
  );
}

// ── chart cards 76/77/79/81 — the generic dual-axis shell ────────────────────────────────────────────────────────
function Card76({ p, onDateChange }: { p: any; onDateChange?: OnDateChange }) {
  const s = p?.timeline ?? {};
  const legend = Array.isArray(s.legend) ? s.legend : [];
  const color = colorFor(legend, TIMELINE_COLORS);
  const pts = Array.isArray(s.points) ? s.points : [];
  const spec: ChartSpec = {
    points: pts,
    labelOf: (pt) => pt?.slot ?? "",
    left: { min: s.tempAxis?.min ?? null, max: s.tempAxis?.max ?? null, ticks: s.tempAxis?.ticks ?? [], label: s.yAxisLabel },
    right: { min: 0, max: 100, ticks: [100, 80, 60, 40, 20, 0], zeroBased: true, label: s.rightYAxisLabel },
    series: seriesFrom(legend, TIMELINE_KEYS, color),
    refLines: [{ axis: "left", value: fin(s.hotspotWarnC), label: String(s.hotspotWarnLabel ?? ""), color: C.coral500 }],
    tooltipRows: (pt) => legend.flatMap((l: any) => {
      const key = String(l?.key ?? ""); const d = TIMELINE_KEYS[key]; if (!d) return [];
      const unit = key === "load" || key === "efficiency" ? "%" : "°C";
      const dec = key === "load" ? 0 : 1;
      return [{ key, label: String(l?.label ?? key), color: color(key), value: `${fx(d.get(pt), dec)}${unit}`, dashed: d.mark === "line-dashed" }];
    }),
  };
  return (
    <DualAxisChartCard
      title={dash(s.title)}
      picker={<Picker initial={{ preset: "today", range: null, resolution: "3-hourly" }} presets={TIMELINE_PRESETS} resolutionOptions={TIMELINE_RES} toDW={timelineToDW} onDateChange={onDateChange} />}
      spec={spec}
      legend={legend}
      opacityKeys={legend.map((l: any) => String(l?.key ?? ""))}
      insight={String(s.insight ?? "")}
    />
  );
}

function Card77({ p, onDateChange }: { p: any; onDateChange?: OnDateChange }) {
  const s = p?.aging ?? {};
  const legend = Array.isArray(s.legend) ? s.legend : [];
  const color = colorFor(legend, AGING_COLORS);
  const pts = Array.isArray(s.points) ? s.points : [];
  const k = s.kpis ?? {};
  const spec: ChartSpec = {
    points: pts,
    labelOf: (pt) => pt?.label ?? "",
    left: { min: s.lolAxis?.min ?? null, max: s.lolAxis?.max ?? null, ticks: s.lolAxis?.ticks ?? [], label: s.yAxisLabel, fmt: (t) => t.toFixed(1) },
    right: { min: s.faaAxis?.min ?? 0, max: s.faaAxis?.max ?? null, ticks: s.faaAxis?.ticks ?? [], zeroBased: true, label: s.rightYAxisLabel, fmt: (t) => t.toFixed(1) },
    series: seriesFrom(legend, AGING_KEYS, color),
    refLines: [{ axis: "right", value: 1, label: String(s.normalRefLabel ?? ""), color: C.neutral500 }],
    area: { axis: "left", accessor: (pt) => pt?.lolPct, color: color("lol") },
    tooltipRows: (pt) => [
      { key: "lol", label: PRESENTATION_LABELS.lossOfLife, color: color("lol"), value: `${fx(pt?.lolPct, 2)}%` },
      { key: "faa", label: PRESENTATION_LABELS.agingFactor, color: color("faa"), value: `${fx(pt?.faa, 1)}×` },
      { key: "peak", label: PRESENTATION_LABELS.hotspotPeak, color: C.sky600, value: `${fx(pt?.hotspotPeakC, 1)}°C`, dashed: true },
    ],
  };
  const kpiStrip = (
    <KpiStatStrip
      cells={[
        { id: "life-used", label: PRESENTATION_LABELS.lifeUsed, value: dash(k.lifeUsedPct), unit: "%", sub: String(k.lifeNote ?? "") },
        { id: "aging-now", label: PRESENTATION_LABELS.agingNow, value: fx(k.agingFactor, 1), unit: "×", sub: PRESENTATION_LABELS.vs1xNormal },
        { id: "delta-window", label: `Δ ${dash(s.windowDays)} days`, value: fin(k.deltaLolPct) != null ? `+${fin(k.deltaLolPct)!.toFixed(2)}%` : "—", sub: PRESENTATION_LABELS.lifeConsumed, valueColor: C.coral500 },
      ]}
    />
  );
  return (
    <DualAxisChartCard
      title={dash(s.title)}
      picker={<Picker initial={{ preset: "this-month", range: null, resolution: "daily" }} presets={AGING_PRESETS} resolutionOptions={AGING_RES} toDW={agingToDW} onDateChange={onDateChange} />}
      kpiStrip={kpiStrip}
      spec={spec}
      legend={legend}
      opacityKeys={legend.map((l: any) => String(l?.key ?? ""))}
      insight={String(s.insight ?? "")}
    />
  );
}

function Card79({ p, onDateChange }: { p: any; onDateChange?: OnDateChange }) {
  const s = p?.regulation ?? {};
  const legend = Array.isArray(s.legend) ? s.legend : [];
  const color = colorFor(legend, REG_COLORS);
  const pts = Array.isArray(s.points) ? s.points : [];
  const kpis = Array.isArray(s.kpis) ? s.kpis : [];
  const spec: ChartSpec = {
    points: pts,
    labelOf: (pt) => pt?.label ?? "",
    left: { min: s.voltageAxis?.min ?? null, max: s.voltageAxis?.max ?? null, ticks: s.voltageAxis?.ticks ?? [], label: s.yAxisLabel, fmt: (t) => t.toFixed(2) },
    right: { min: 0, max: s.tapAxis?.max ?? null, ticks: s.tapAxis?.ticks ?? [], zeroBased: true, label: s.rightYAxisLabel },
    series: seriesFrom(legend, REG_KEYS, color),
    band: { axis: "left", top: fin(s.bandHighKv), bottom: fin(s.bandLowKv), color: C.sage500 },
    refLines: [{ axis: "left", value: fin(s.setpointKv), label: PRESENTATION_LABELS.setPointVoltage, color: C.sage500, placement: "below" }],
    dots: { axis: "left", accessor: (pt) => pt?.voltageKv, when: (pt) => pt?.excursion === true, color: C.coral500 },
    edgeToEdgeX: true,
    marginLeft: 56,
    tooltipRows: (pt) => [
      { key: "voltage", label: PRESENTATION_LABELS.voltage, color: color("voltage"), value: `${fx(pt?.voltageKv, 2)} kV` },
      { key: "tap", label: PRESENTATION_LABELS.tapPosition, color: color("tap"), value: dash(pt?.tap) },
    ],
    tooltipTag: (pt) => (pt?.excursion === true ? String(s.outOfBandLabel ?? "") : null),
  };
  const kpiStrip = <KpiStatStrip cells={kpis.map((kk: any, i: number) => ({ id: String(kk?.id ?? i), label: String(kk?.label ?? ""), value: kk?.value != null && kk?.value !== "" ? String(kk.value) : "—", unit: kk?.unit || undefined }))} />;
  return (
    <DualAxisChartCard
      title={dash(s.title)}
      picker={<Picker initial={{ preset: "today", range: null, resolution: "hourly", shift: "all" }} presets={TAP_PRESETS} resolutionOptions={TAP_RES} shiftOptions={TAP_SHIFT} shiftWhenResolution="shift" toDW={tapToDW} onDateChange={onDateChange} />}
      kpiStrip={kpiStrip}
      spec={spec}
      legend={legend}
      opacityKeys={legend.map((l: any) => String(l?.key ?? ""))}
      insight={String(s.insight ?? "")}
    />
  );
}

function Card81({ p, onDateChange }: { p: any; onDateChange?: OnDateChange }) {
  const s = p?.activity ?? {};
  const legend = Array.isArray(s.legend) ? s.legend : [];
  const color = colorFor(legend, ACTIVITY_COLORS);
  const pts = Array.isArray(s.points) ? s.points : [];
  const kpis = Array.isArray(s.kpis) ? s.kpis : [];
  const spec: ChartSpec = {
    points: pts,
    labelOf: (pt) => pt?.label ?? "",
    left: { min: 0, max: s.countAxis?.max ?? null, ticks: s.countAxis?.ticks ?? [], zeroBased: true, label: s.yAxisLabel },
    right: { min: s.cumAxis?.min ?? null, max: s.cumAxis?.max ?? null, ticks: s.cumAxis?.ticks ?? [], label: s.rightYAxisLabel },
    series: seriesFrom(legend, ACTIVITY_KEYS, color),
    tooltipRows: (pt) => [
      { key: "today", label: PRESENTATION_LABELS.tapOperations, color: color("today"), value: dash(pt?.count) },
      { key: "total", label: PRESENTATION_LABELS.totalCount, color: color("total"), value: dash(pt?.cumTotal) },
    ],
  };
  const kpiStrip = <KpiStatStrip cells={kpis.map((kk: any, i: number) => ({ id: String(kk?.id ?? i), label: String(kk?.label ?? ""), value: kk?.value != null && kk?.value !== "" ? String(kk.value) : "—", unit: kk?.unit || undefined }))} />;
  return (
    <DualAxisChartCard
      title={dash(s.title)}
      picker={<Picker initial={{ preset: "today", range: null, resolution: "hourly", shift: "all" }} presets={TAP_PRESETS} resolutionOptions={TAP_RES} shiftOptions={TAP_SHIFT} shiftWhenResolution="shift" toDW={tapToDW} onDateChange={onDateChange} />}
      kpiStrip={kpiStrip}
      spec={spec}
      legend={legend}
      opacityKeys={legend.map((l: any) => String(l?.key ?? ""))}
      insight={String(s.insight ?? "")}
    />
  );
}

export const CARDS: Record<number, (p: any, onDateChange?: OnDateChange) => React.ReactNode> = {
  74: (p) => <Card74 p={p} />,
  75: (p) => <Card75 p={p} />,
  76: (p, od) => <Card76 p={p} onDateChange={od} />,
  77: (p, od) => <Card77 p={p} onDateChange={od} />,
  78: (p) => <Card78 p={p} />,
  79: (p, od) => <Card79 p={p} onDateChange={od} />,
  80: (p) => <Card80 p={p} />,
  81: (p, od) => <Card81 p={p} onDateChange={od} />,
};
