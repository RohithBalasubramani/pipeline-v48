// prim/energy.tsx — Energy family (cards 12,13,14,15,16,17,39,40,41,42) on PRIMITIVES ONLY. [primitives-only port]
//
// Each card mounts CMD_V2 chart primitives directly from its completed payload; header/legends/colors/values ride the
// payload (AI-morphable). Two cards are BARREL primitives mounted directly (39 TodaysEnergyCard, 42 LoadAnomaliesChart)
// with the retired fill's honest-blank coercion reimplemented here; the rest are recomposed from primitives (rail list,
// FlowSankey/EfficiencyBand/SankeyLegend, TickProgressBar/KpiStatStrip). The chart-heavy 16/17/40 live in ./energy-trend.
// Honesty: missing scalar → '—' via fin()/fmtNum(); the numeric leaves the primitives read UNGUARDED for arithmetic are
// coerced finite (the documented empty state), never fabricated.
import React from "react";
import {
  AiSummary,
  Card,
  CardHeader,
  CHART_COLORS,
  composeMetricHeader,
  composeMetricText,
  composeValueUnit,
  EfficiencyBand,
  FlowSankey,
  KpiStatStrip,
  LoadAnomaliesChart,
  presetRange,
  SamplingPicker,
  SankeyLegend,
  StatusBadge,
  TickProgressBar,
  TodaysEnergyCard,
  type SamplingSelection,
  type StatusTone,
  type TickProgressSegment,
} from "@cmd-v2/components/charts/primitives";
import { fin, dash, fmtNum } from "./shared";
import { periodToWindow, samplingToWindow, type DateWindow } from "./energy-date";
import { PowerEnergyAnalysis40, EnergyTrend16, DemandProfile17 } from "./energy-trend";

const arr = (v: any): any[] => (Array.isArray(v) ? v : []);
const toneOf = (t: any): StatusTone =>
  (["fail", "critical", "warning", "success", "info", "neutral"].includes(String(t)) ? t : "neutral") as StatusTone;
/** A structured MetricHeader → text; a plain string → itself; anything else → ''. */
const headerText = (h: any): string =>
  h && typeof h === "object" ? composeMetricHeader(h) : typeof h === "string" ? h : "";

// ── Card 12 — Energy Input & Distribution rail list (vm.sources/consumers rows + utilization bars) ────────────────
function RailRow({ label, valueText, pct, color, indented }:
  { label: any; valueText: string; pct: any; color?: string; indented?: boolean }) {
  const w = fin(pct);
  return (
    <div className="flex items-center gap-2 py-1" style={{ paddingLeft: indented ? 16 : 0 }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: color ?? "transparent", flexShrink: 0, display: "inline-block" }} />
      <span className="min-w-0 flex-1 truncate" style={{ fontSize: 12 }}>{dash(label)}</span>
      {w != null ? (
        <span className="block h-1.5 w-16 shrink-0 overflow-hidden rounded" style={{ background: CHART_COLORS.cream200 }}>
          <span style={{ display: "block", height: "100%", width: `${Math.max(0, Math.min(100, w))}%`, background: color ?? CHART_COLORS.teal500, borderRadius: 4 }} />
        </span>
      ) : null}
      <span className="shrink-0 tabular-nums" style={{ fontSize: 12, fontVariantNumeric: "tabular-nums" }}>{valueText}</span>
    </div>
  );
}
function SectionHeader({ left, right }: { left: any; right: any }) {
  return (
    <div className="flex items-center justify-between pb-1 pt-2 text-[10px]"
      style={{ opacity: 0.6, textTransform: "uppercase", letterSpacing: "0.04em" }}>
      <span className="truncate">{String(left ?? "")}</span>
      <span className="shrink-0 pl-2">{String(right ?? "")}</span>
    </div>
  );
}
function TotalRow({ label, valueText, unit }: { label: any; valueText: string; unit?: string }) {
  return (
    <div className="mt-1 flex items-center justify-between border-t pt-1 text-[12px] font-semibold"
      style={{ borderColor: CHART_COLORS.cream400 }}>
      <span className="truncate">{dash(label)}</span>
      <span className="shrink-0 tabular-nums">{composeValueUnit(valueText, unit)}</span>
    </div>
  );
}
function EnergyInputDistribution12({ payload }: { payload: any }) {
  const vm = payload?.rail?.vm ?? payload?.vm ?? {};
  const sources = arr(vm.sources);
  const consumers = arr(vm.consumers);
  return (
    <Card className="h-full" overflow="hidden">
      <CardHeader title={dash(vm.inputCardTitle)} />
      <div className="scroll-on-hover flex min-h-0 flex-1 flex-col overflow-y-auto pt-2">
        <RailRow label={vm.allRowLabel} valueText={fmtNum(vm.allTotalKwh, 0)} pct={vm.allUtilizationPct} color={vm.allRowColor} />
        <div className="mt-2 flex flex-col gap-0.5">
          <SectionHeader left={vm.sourcesSection?.groupLabel} right={headerText(vm.sourcesSection?.columnHeader)} />
          {sources.map((s: any, i: number) => (
            <RailRow key={String(s?.id ?? i)} label={s?.label} valueText={fmtNum(s?.totalKwh, 0)} pct={s?.utilizationPct} color={s?.color} />
          ))}
          <TotalRow label={vm.supplied?.label} valueText={fmtNum(vm.totalSuppliedKwh, 0)} unit={vm.supplied?.unit} />
        </div>
        <div className="mt-3 flex flex-col gap-0.5">
          <SectionHeader left={vm.consumersSection?.groupLabel} right={headerText(vm.consumersSection?.columnHeader)} />
          {consumers.map((g: any, gi: number) => (
            <div key={String(g?.id ?? gi)} className="flex flex-col gap-0.5">
              <RailRow label={g?.label} valueText={fmtNum(g?.totalKwh, 0)} pct={g?.utilizationPct} color={g?.color} />
              {arr(g?.meters).map((m: any, mi: number) => (
                <RailRow key={String(m?.id ?? mi)} indented label={m?.label} valueText={fmtNum(m?.kwh, 0)} pct={m?.utilizationPct} color={g?.color} />
              ))}
            </div>
          ))}
          <TotalRow label={vm.consumed?.label} valueText={fmtNum(vm.totalConsumedKwh, 0)} unit={vm.consumed?.unit} />
        </div>
      </div>
    </Card>
  );
}

// ── Card 13 — Energy Flow Diagram (AiSummary + EfficiencyBand ribbon + FlowSankey + SankeyLegend) ──────────────────
function KpiBlock({ caption, value, unit, align }: { caption: any; value: any; unit: any; align: "left" | "right" }) {
  return (
    <div className={`flex shrink-0 flex-col gap-1 ${align === "right" ? "items-end text-right" : "items-start text-left"}`}>
      <span className="text-[10px] font-bold uppercase" style={{ opacity: 0.6, letterSpacing: "0.04em" }}>{String(caption ?? "")}</span>
      <span className="flex items-baseline gap-1">
        <span className="text-[22px] font-bold leading-none" style={{ color: CHART_COLORS.teal900 ?? undefined }}>{fmtNum(value, 0)}</span>
        <span className="text-[12px]" style={{ color: CHART_COLORS.teal500 }}>{String(unit ?? "")}</span>
      </span>
    </div>
  );
}
function EnergyFlowDiagram13({ payload }: { payload: any }) {
  const vm = payload?.flow?.vm ?? payload?.vm ?? {};
  const kpis = vm.kpis ?? {};
  const band = kpis.band ?? {};
  const sankey = vm.sankey && typeof vm.sankey === "object" ? vm.sankey : { nodes: [], links: [] };
  const legend = arr(vm.legend).map((g: any) => ({ label: String(g?.label ?? ""), items: arr(g?.items) }));
  return (
    <Card className="h-full" overflow="hidden">
      <CardHeader title={dash(vm.flowCardTitle)} />
      <div className="mt-2 flex min-h-0 flex-1 flex-col gap-3">
        {vm.aiSummary ? <AiSummary text={String(vm.aiSummary)} /> : null}
        <div className="flex w-full items-center gap-6 rounded-[8px] px-5 py-3"
          style={{ background: CHART_COLORS.cream50 ?? undefined, border: `1px dashed ${CHART_COLORS.cream400}` }}>
          <KpiBlock caption={kpis.sourceInputCaption} value={kpis.sourceInputKwh} unit={kpis.unit} align="left" />
          <div className="min-w-0 flex-1">
            {(() => {
              // Efficiency/loss render ONLY when the source↔feeder pairing is physically plausible (0–100%). A blank
              // source gives 0 % (fabricated) and an under-metered / HT-vs-LV source gives >100 % (impossible: feeder
              // output cannot exceed source input). Either way the honest answer is "—", not a made-up number.
              const eff = fin(kpis.efficiencyPct);
              if (eff == null || eff < 0 || eff > 100) {
                return (
                  <div className="text-center text-[13px]" style={{ color: CHART_COLORS.slate500 ?? undefined }}>
                    {String(band.efficiencyLabel ?? "Efficiency")} — · {String(band.lossLabel ?? "Loss")} —
                  </div>
                );
              }
              return (
                <EfficiencyBand
                  efficiencyPct={eff}
                  lossKw={fin(kpis.lossKwh) ?? 0}
                  lossPct={fin(kpis.lossPct) ?? 0}
                  labels={{ efficiency: band.efficiencyLabel, loss: band.lossLabel, lostSuffix: band.lostSuffix }}
                  colors={{ fillPrimary: band.fillPrimary, fillLoss: band.fillLoss }}
                  lossUnit={band.lossUnit} pctUnit={band.pctUnit} />
              );
            })()}
          </div>
          <KpiBlock caption={kpis.feederOutputCaption} value={kpis.feederOutputKwh} unit={kpis.unit} align="right" />
        </div>
        <div className="min-h-0 flex-1 overflow-hidden">
          <FlowSankey data={sankey} selectedNodeId={payload?.flow?.selectedNodeId ?? null} valueUnit={vm.stageUnit ?? "kWh"} />
        </div>
        <SankeyLegend groups={legend} />
      </div>
    </Card>
  );
}

// ── Cards 14/15 — Energy Progress (headline + TickProgressBar + KpiStatStrip + AiSummary + SamplingPicker) ─────────
function toTickSegments(segments: any, capacityValue: any, capacityUsedValue: any): TickProgressSegment[] {
  const filled = arr(segments).map((s: any) => ({ id: String(s?.id ?? ""), color: s?.color, weight: fin(s?.value) ?? 0 }));
  const cap = fin(capacityValue);
  if (cap == null) return filled;
  const used = fin(capacityUsedValue) ?? filled.reduce((a, s) => a + s.weight, 0);
  const remainder = Math.max(0, cap - used);
  return remainder > 0 ? [...filled, { id: "remaining", color: CHART_COLORS.cream300, weight: remainder }] : filled;
}
function EnergyProgress({ payload, onDateChange }: { payload: any; onDateChange?: (dw: DateWindow) => void }) {
  const view = payload?.view ?? payload?.data ?? payload ?? {};
  const [sampling, setSampling] = React.useState<SamplingSelection>(() => ({ preset: "today", range: presetRange("today", new Date()) }));
  const markerPct = fin(view.markerPct);
  return (
    <Card className="h-full" overflow="hidden" style={{ padding: 16, rowGap: 12 }}>
      <CardHeader title={dash(view.title)} action={
        <div className="flex items-center gap-2">
          {view.periodLabel ? (
            <SamplingPicker value={sampling} presets={view.rangeOptions} resolutionOptions={view.resolutionOptions}
              shiftOptions={view.shiftOptions} shiftWhenResolution="by-shift" align="end"
              onChange={(next) => { setSampling(next); try { onDateChange && onDateChange(samplingToWindow(next)); } catch { /* keep */ } }} />
          ) : null}
          {view.statusLabel && view.statusTone ? <StatusBadge label={String(view.statusLabel)} tone={toneOf(view.statusTone)} /> : null}
        </div>
      } />
      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-1">
          <span className="text-[26px] font-bold leading-none">{dash(view.value)}</span>
          <span className="text-[12px]" style={{ opacity: 0.7 }}>{String(view.valueUnit ?? "")}</span>
          {view.target ? <span className="text-[16px]" style={{ opacity: 0.6 }}>/{dash(view.target)}</span> : null}
          {view.target && view.targetUnit ? <span className="text-[12px]" style={{ opacity: 0.7 }}>{String(view.targetUnit)}</span> : null}
        </div>
        {view.markerLabel ? (
          <span className="text-[11px]" style={{ opacity: 0.6 }}>
            {typeof view.markerLabel === "object" ? composeMetricText(view.markerLabel) : String(view.markerLabel)}
          </span>
        ) : null}
      </div>
      <TickProgressBar segments={toTickSegments(view.segments, view.capacityValue, view.capacityUsedValue)}
        marker={markerPct != null ? { pct: markerPct } : null} />
      <div className="border-t pt-3" style={{ borderColor: CHART_COLORS.cream400 }}>
        <KpiStatStrip height="auto" swatchShape="round" withCellDividers={false} withBottomDivider={false}
          cells={arr(view.metrics).map((m: any) => ({ id: String(m?.id ?? m?.label ?? ""), label: String(m?.label ?? ""),
            value: dash(m?.value), unit: m?.unit, sub: m?.sub, swatch: m?.color }))} />
      </div>
      {view.insight ? (
        <div className="mt-auto border-t pt-3" style={{ borderColor: CHART_COLORS.cream400 }}>
          <AiSummary text={String(view.insight)} density="compact" />
        </div>
      ) : null}
    </Card>
  );
}

// ── Card 41 — Input vs Output Energy (2-col headline + TickProgressBar + below-bar labels + KpiStatStrip + AiSummary)
function InputOutputEnergy41({ payload }: { payload: any }) {
  const d = payload?.data ?? {};
  const hv = fin(d.hvInputKw), lv = fin(d.lvOutputKw);
  const lossKw = hv != null && lv != null ? Math.max(0, hv - lv) : null;
  const deliveredPct = hv != null && hv > 0 && lv != null ? Math.max(0, Math.min(100, (lv / hv) * 100)) : null;
  const lostPct = hv != null && hv > 0 && lv != null ? Math.max(0, Math.min(100, ((hv - lv) / hv) * 100)) : null;
  const powerUnit = d.powerUnit, percentUnit = d.percentUnit, energyUnit = d.energyUnit;
  const segments: TickProgressSegment[] = [
    { id: "delivered", color: d.deliveredColor, weight: lv ?? 0 },
    { id: "loss", color: d.lossColor, weight: lossKw ?? 0 },
  ];
  return (
    <Card className="h-full" overflow="hidden" style={{ padding: 16, rowGap: 12 }}>
      <CardHeader title={dash(d.title)} dividerTone="strong" />
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col items-start gap-1.5">
          <span className="text-[10px] font-bold uppercase" style={{ opacity: 0.6 }}>{String(d.hvInputLabel ?? "")}</span>
          <div className="flex items-baseline gap-1">
            <span className="text-[26px] font-bold leading-none">{fmtNum(d.hvInputKw, 1)}</span>
            <span className="text-[12px]" style={{ opacity: 0.7 }}>{String(powerUnit ?? "")}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="text-[10px] font-bold uppercase" style={{ opacity: 0.6 }}>{String(d.lvOutputLabel ?? "")}</span>
          <div className="flex items-baseline gap-1">
            <span className="text-[26px] font-bold leading-none">{fmtNum(d.lvOutputKw, 1)}</span>
            <span className="text-[12px]" style={{ opacity: 0.7 }}>{String(powerUnit ?? "")}</span>
          </div>
        </div>
      </div>
      <TickProgressBar segments={segments} marker={{ pct: deliveredPct ?? 0 }} />
      <div className="flex items-center justify-between text-[12px]">
        <div className="flex items-baseline gap-1">
          <span className="font-semibold" style={{ color: d.deliveredColor }}>{composeValueUnit(fmtNum(d.lvOutputKw, 1), powerUnit)}</span>
          <span style={{ color: d.descriptorColor, opacity: 0.85 }}>· {composeValueUnit(fmtNum(deliveredPct, 1), percentUnit, "")} {String(d.deliveredDescriptor ?? "")}</span>
        </div>
        <div className="flex items-baseline gap-1">
          <span className="font-semibold" style={{ color: d.lostValueColor }}>{composeValueUnit(fmtNum(lossKw, 1), powerUnit)}</span>
          <span style={{ color: d.descriptorColor, opacity: 0.85 }}>· {composeValueUnit(fmtNum(lostPct, 1), percentUnit, "")} {String(d.lostDescriptor ?? "")}</span>
        </div>
      </div>
      <div className="border-t pt-3" style={{ borderColor: CHART_COLORS.cream500 ?? CHART_COLORS.cream400 }}>
        <KpiStatStrip height="auto" swatchShape="round" withCellDividers={false} withBottomDivider={false}
          cells={[
            { id: "loss", label: String(d.lossLabel ?? ""), value: fmtNum(d.lossKwh, 0), unit: energyUnit },
            { id: "expected-loss", label: String(d.expectedLossLabel ?? ""), value: fmtNum(d.expectedLossKwh, 0), unit: energyUnit },
            { id: "efficiency", label: String(d.efficiencyLabel ?? ""), value: fmtNum(d.efficiencyPct, 0), unit: percentUnit },
          ]} />
      </div>
      {d.insight ? (
        <div className="mt-auto border-t pt-3" style={{ borderColor: CHART_COLORS.cream400 }}>
          <AiSummary text={String(d.insight)} density="compact" />
        </div>
      ) : null}
    </Card>
  );
}

// ── Card 39 — Today's Energy (BARREL primitive TodaysEnergyCard, honest-blank-safe by Number.isFinite) ────────────
function todaysEnergyData(payload: any): any {
  const d = payload?.data ?? {};
  return { ...d, period: String(d.period ?? ""), periodOptions: arr(d.periodOptions) };
}
// ── Card 42 — Load Anomalies (BARREL primitive LoadAnomaliesChart; the numeric leaves it reads UNGUARDED forced finite)
function loadAnomaliesData(payload: any): any {
  const a = payload?.data ?? {};
  return {
    ...a,
    period: String(a.period ?? "today"), periodOptions: arr(a.periodOptions),
    labels: a.labels ?? {}, colors: a.colors ?? {},
    actualLoad: arr(a.actualLoad), expectedLoad: arr(a.expectedLoad), expectedRange: arr(a.expectedRange), anomalies: arr(a.anomalies),
    maxThresholdPct: fin(a.maxThresholdPct) ?? 0, presentValuePct: fin(a.presentValuePct) ?? 0, loadFactorPct: fin(a.loadFactorPct) ?? 0,
    surgeEvents: fin(a.surgeEvents) ?? 0, dipEvents: fin(a.dipEvents) ?? 0, yMin: fin(a.yMin) ?? 0, yMax: fin(a.yMax) ?? 100,
  };
}

export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  12: (p) => <EnergyInputDistribution12 payload={p} />,
  13: (p) => <EnergyFlowDiagram13 payload={p} />,
  14: (p, od) => <EnergyProgress payload={p} onDateChange={od} />,
  15: (p, od) => <EnergyProgress payload={p} onDateChange={od} />,
  16: (p, od) => <EnergyTrend16 payload={p} onDateChange={od} />,
  17: (p, od) => <DemandProfile17 payload={p} onDateChange={od} />,
  39: (p, od) => <TodaysEnergyCard data={todaysEnergyData(p)} onPeriodChange={(period: string) => od?.(periodToWindow(period))} />,
  40: (p, od) => <PowerEnergyAnalysis40 payload={p} onDateChange={od} />,
  41: (p) => <InputOutputEnergy41 payload={p} />,
  42: (p, od) => (
    <LoadAnomaliesChart data={loadAnomaliesData(p)}
      onPeriodChange={(period: string) => od?.(periodToWindow(period))}
      onCustomRangeChange={(range: any) => range && od?.({ range: "custom-range", start: range.start, end: range.end, sampling: "day" })} />
  ),
};
