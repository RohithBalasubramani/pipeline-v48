// prim/pq-feeder.tsx — Feeder Power-Quality tab (cards 47,48,49) on PRIMITIVES ONLY. [primitives-only port]
//
// USER DIRECTIVE (2026-07-12): no page cards. Each card mounts CMD_V2 chart PRIMITIVES directly from its completed
// payload; every label/number-format/colour rides the payload (AI-morphable). Barrel-only imports — the legacy fill
// pulled PowerQualityCard/viewModel/tokens/sampling from @cmd-v2/pages/**, which is FORBIDDEN here, so:
//   47 PowerQualityCard → reimplemented from KpiStatStrip + SpectrumBar rows + KeyValueRowsCard + StatusPill (the
//      exact composition PowerQualityCard.tsx uses), reading snapshot.presentation.* with safe fallbacks + fin()/dash
//      so an honest-blank leaf renders the payload placeholder, never a `"—".toFixed` crash.
//   48 DistortionProfileChart / 49 LoadImpactChart → barrel primitives, mounted with the payload slice through a
//      light normalizer that guarantees the always-draw invariant (views object, valid selected view, array-safe
//      series/yTicks/watchLines) the old fill got from createPowerQualityViewModel — reimplemented crash-guards, NOT
//      seeded data (null threshold lines drop, blank stats → '—', empty views stay empty chrome).
// Date control: 48/49 carry a real SamplingPicker; its onSamplingChange → host date_window → onDateChange (reimplements
// feeder-power-quality/date-window.ts samplingToDateWindow). 47 has no date control (pure now-snapshot).
import React from "react";
import {
  Card,
  CardBodySkeleton,
  CHART_COLORS,
  DistortionProfileChart,
  KeyValueRowsCard,
  KpiStatStrip,
  LoadImpactChart,
  SpectrumBar,
  StatusPill,
  TYPOGRAPHY_FAMILY,
  UNITS,
  composeValueUnit,
  type SamplingSelection,
} from "@cmd-v2/components/charts/primitives";
import { dash, fin } from "./shared";

// ── card-47 chrome (geometry/typography only — colours ride the payload palette; from PowerQualityCard.tsx) ─────────
const CARD_HEADER_STYLE: React.CSSProperties = {
  fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 15, fontWeight: 400,
  color: CHART_COLORS.teal900, letterSpacing: -1.05, lineHeight: "normal",
};
const SECTION_LABEL_STYLE: React.CSSProperties = {
  fontFamily: "IBM Plex Sans, system-ui, sans-serif", fontWeight: 700, fontSize: 12,
  color: CHART_COLORS.teal900, lineHeight: 1,
};
const SECTION_SUB_STYLE: React.CSSProperties = {
  fontFamily: "IBM Plex Sans, system-ui, sans-serif", fontWeight: 400, fontSize: 12,
  color: CHART_COLORS.teal700 ?? CHART_COLORS.tealLabel600, lineHeight: 1,
};
const SPECTRUM_VALUE_STYLE: React.CSSProperties = {
  fontFamily: "Space Mono, ui-monospace, monospace", fontWeight: 700, fontSize: 13,
  lineHeight: "normal", textAlign: "right",
};
const X_AXIS_STYLE: React.CSSProperties = {
  fontFamily: "Space Mono, ui-monospace, monospace", fontWeight: 400, fontSize: 12,
  color: CHART_COLORS.sky400, lineHeight: "normal",
};
const X_AXIS_LABEL_STYLE: React.CSSProperties = {
  fontFamily: "IBM Plex Sans, system-ui, sans-serif", fontWeight: 600, fontSize: 8,
  color: CHART_COLORS.sky400, letterSpacing: 0.4, textTransform: "uppercase",
};
const SECTION_DIVIDER_STYLE: React.CSSProperties = {
  fontFamily: "Space Mono, ui-monospace, monospace", fontWeight: 400, fontSize: 12,
  color: CHART_COLORS.teal900, letterSpacing: -0.84,
};

// IEEE 519 LV default THD limits — the reference threshold each spectrum bar falls back to when the reading carries no
// limitPct (chrome, NOT a measured value; mirrors PQ_LIMITS.{iThdPct,vThdPct,individualHarmonicPct} = 8/8/8).
const SPECTRUM_DEFAULT_LIMIT = { iThd: 8, vThd: 8, h5: 8, h7: 8 } as const;
const PILL_TONES = new Set(["normal", "alarm", "watch", "info"]);

/** ''/null → the payload's placeholder glyph (honest-blank); anything else verbatim. */
const orPh = (v: any, ph: string): string => (v == null || v === "" ? ph : String(v));

function toneColor(tone: any, palette: any): string | undefined {
  if (tone === "critical") return palette?.cellCritical;
  if (tone === "watch") return palette?.cellWatch;
  if (tone === "ok") return palette?.cellOk;
  return undefined;
}
function toneBadge(tone: any, badge: any, palette: any):
  { label: string; background?: string; color?: string } | undefined {
  if (!badge) return undefined;
  if (tone === "critical") return { label: String(badge.label ?? ""), background: palette?.badgeCriticalBg, color: palette?.badgeCriticalFg };
  if (tone === "watch") return { label: String(badge.label ?? ""), background: palette?.badgeWatchBg, color: palette?.badgeWatchFg };
  return undefined;
}

// ── card 47 sub-widgets ────────────────────────────────────────────────────────────────────────────────────────────
function PqSectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-2 w-full">
      <span className="whitespace-nowrap" style={SECTION_DIVIDER_STYLE}>{label}</span>
      <span className="flex-1 min-w-0" style={{ height: 0, borderTop: `1px dashed ${CHART_COLORS.cream300}` }} />
    </div>
  );
}

function PqSpectrumRow({ rowPres, reading, defaultLimit, axis, palette, ph }:
  { rowPres: any; reading: any; defaultLimit: number; axis: any; palette: any; ph: string }) {
  const value = fin(reading?.valuePct);
  const limit = fin(reading?.limitPct) ?? defaultLimit;
  const scaleMax = fin(reading?.scaleMaxPct) ?? fin(axis?.scaleMax) ?? Math.max(limit * 2, 1);
  const isOver = value != null && value >= limit;
  const valueColor = isOver ? (palette?.spectrumOverLimit ?? CHART_COLORS.coral700) : (palette?.valueDefault ?? CHART_COLORS.teal900);
  const decimals = fin(rowPres?.valueDecimals) ?? 0;
  return (
    <div className="flex w-full items-center gap-3 pb-3">
      <div className="flex shrink-0 flex-col" style={{ minWidth: 52, lineHeight: 0.998 }}>
        <span style={SECTION_LABEL_STYLE}>{rowPres?.primary ?? ""}</span>
        <span style={SECTION_SUB_STYLE}>{rowPres?.sub ?? ""}</span>
      </div>
      <SpectrumBar value={value ?? 0} threshold={limit} scaleMax={scaleMax}
        tone={isOver ? "warning" : "ok"} width={256} className="shrink-0" />
      <div className="ml-auto" style={{ ...SPECTRUM_VALUE_STYLE, color: valueColor, minWidth: 50 }}>
        {value != null ? composeValueUnit(value.toFixed(decimals), UNITS.percent, "") : ph}
      </div>
    </div>
  );
}

function PqSpectrumXAxis({ axis }: { axis: any }) {
  const fractions = Array.isArray(axis?.tickFractions) ? axis.tickFractions : [];
  const scaleMax = fin(axis?.scaleMax) ?? 0;
  const tickDecimals = fin(axis?.tickDecimals) ?? 0;
  const ticks = fractions.map((f: any) => (fin(f) ?? 0) * scaleMax);
  return (
    <div className="flex w-full items-center gap-3">
      <span className="shrink-0" style={{ ...X_AXIS_LABEL_STYLE, minWidth: 52 }}>{axis?.label ?? ""}</span>
      <div className="shrink-0 relative" style={{ width: 256, height: 18 }}>
        {ticks.map((t: number, i: number) => (
          <span key={i} className="absolute -translate-x-1/2"
            style={{ left: `${ticks.length > 1 ? (i / (ticks.length - 1)) * 100 : 0}%`, top: 0, ...X_AXIS_STYLE }}>
            {t.toFixed(tickDecimals)}
          </span>
        ))}
      </div>
      <div className="ml-auto" style={{ minWidth: 50 }} />
    </div>
  );
}

// ── card 47 — PowerQualityCard reimplemented (Card + KpiStatStrip×2 + SpectrumBar rows + KeyValueRowsCard) ──────────
function Card47({ payload }: { payload: any }) {
  const snap = payload?.snapshot ?? {};
  const pres = snap.presentation ?? {};
  const palette = pres.palette ?? {};
  const cs = pres.complianceStrip ?? {};
  const ph = cs.placeholder ?? "—";
  const spectrum = pres.spectrum ?? {};
  const axis = spectrum.axis ?? {};
  const vq = pres.voltageQuality ?? {};
  const sm = pres.sourceMitigation ?? {};

  const badge = snap.ieeeBadge;
  const badgeLabel = badge?.label;
  const badgeTone = PILL_TONES.has(badge?.tone) ? badge.tone : "info";
  const loading = payload?.loading === true || snap.availability === "loading";

  const trendPct = fin(snap.trendPctPerHour);
  const trendDecimals = fin(cs.trendDecimals) ?? 1;
  const flickerVal = fin(snap.flickerPst?.value);
  const flickerPeak = fin(snap.flickerPst?.peakToday);
  const flickerLimit = fin(snap.flickerPst?.limit);
  const crestVal = fin(snap.crestFactor?.value);
  const crestIdeal = fin(snap.crestFactor?.ideal);

  return (
    <Card
      className="h-full"
      style={{ borderRadius: 8, padding: 15, display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}
    >
      <header className="flex w-full items-center justify-between pb-3">
        <h3 style={CARD_HEADER_STYLE}>{dash(pres.title)}</h3>
        {badgeLabel ? <StatusPill label={String(badgeLabel)} tone={badgeTone} leading="square" size="micro" /> : null}
      </header>

      {loading ? (
        <CardBodySkeleton kpiCells={3} className="pt-1" />
      ) : (
        <>
          {/* Compliance / Trend / Severity */}
          <KpiStatStrip
            withCellDividers dividerStyle="solid" withOuterBorder withBottomDivider={false} height="auto" density="dense"
            cells={[
              {
                id: "compliance", label: cs.complianceLabel ?? "",
                value: snap.ieeeState === "fail" ? (cs.complianceWords?.fail ?? ph)
                  : snap.ieeeState === "pass" ? (cs.complianceWords?.pass ?? ph) : ph,
                sub: snap.ieeeConstraint || undefined,
                valueColor: snap.ieeeState === "fail" ? palette.complianceFail : palette.valueDefault,
              },
              {
                id: "trend", label: cs.trendLabel ?? "", value: orPh(snap.trendLabel, ph),
                sub: trendPct != null
                  ? composeValueUnit(`${trendPct >= 0 ? (cs.trendPositiveSign ?? "+") : ""}${trendPct.toFixed(trendDecimals)}`, UNITS.percentPerHour, " ")
                  : undefined,
                valueColor: palette.valueDefault,
              },
              {
                id: "severity", label: cs.severityLabel ?? "", value: orPh(snap.severityLabel, ph),
                sub: snap.severityAction || undefined,
                valueColor: snap.severityLabel && snap.severityLabel === cs.severityHighWord ? palette.severityHigh : palette.valueDefault,
              },
            ]}
          />

          {/* Total Distortion */}
          <PqSectionDivider label={spectrum.totalDistortionLabel ?? ""} />
          <PqSpectrumRow rowPres={spectrum.iThd} reading={snap.iThd} defaultLimit={SPECTRUM_DEFAULT_LIMIT.iThd} axis={axis} palette={palette} ph={ph} />
          <PqSpectrumRow rowPres={spectrum.vThd} reading={snap.vThd} defaultLimit={SPECTRUM_DEFAULT_LIMIT.vThd} axis={axis} palette={palette} ph={ph} />
          <PqSpectrumXAxis axis={axis} />

          {/* Individual Order */}
          <PqSectionDivider label={spectrum.individualOrderLabel ?? ""} />
          <PqSpectrumRow rowPres={spectrum.h5} reading={snap.h5} defaultLimit={SPECTRUM_DEFAULT_LIMIT.h5} axis={axis} palette={palette} ph={ph} />
          <PqSpectrumRow rowPres={spectrum.h7} reading={snap.h7} defaultLimit={SPECTRUM_DEFAULT_LIMIT.h7} axis={axis} palette={palette} ph={ph} />
          <PqSpectrumXAxis axis={axis} />

          {/* Voltage Quality */}
          <PqSectionDivider label={vq.sectionLabel ?? ""} />
          <KpiStatStrip
            withCellDividers dividerStyle="solid" withOuterBorder withBottomDivider={false} height="auto" density="dense"
            cells={[
              {
                id: "flicker-pst", label: vq.flickerLabel ?? "",
                value: flickerVal != null ? flickerVal.toFixed(fin(vq.flickerValueDecimals) ?? 0) : ph,
                sub: flickerPeak != null && flickerLimit != null
                  ? `${vq.peakLabel ?? "peak"} ${flickerPeak.toFixed(fin(vq.peakDecimals) ?? 0)}${vq.subSeparator ?? " · "}${vq.limLabel ?? "lim"} ${flickerLimit.toFixed(fin(vq.limDecimals) ?? 0)}`
                  : undefined,
                valueColor: toneColor(snap.flickerPst?.tone, palette) ?? palette.valueDefault,
                badge: toneBadge(snap.flickerPst?.tone, snap.flickerPst?.statusBadge, palette),
              },
              {
                id: "crest-factor", label: vq.crestLabel ?? "",
                value: crestVal != null ? crestVal.toFixed(fin(vq.crestValueDecimals) ?? 0) : ph,
                sub: crestIdeal != null ? `${vq.idealLabel ?? "ideal"} ${crestIdeal.toFixed(fin(vq.idealDecimals) ?? 0)}` : undefined,
                valueColor: toneColor(snap.crestFactor?.tone, palette) ?? palette.valueDefault,
                badge: toneBadge(snap.crestFactor?.tone, snap.crestFactor?.statusBadge, palette),
              },
            ]}
          />

          {/* Source & Mitigation */}
          <PqSectionDivider label={sm.sectionLabel ?? ""} />
          <KeyValueRowsCard
            rows={[
              { label: sm.likelySourceLabel ?? "", value: orPh(snap.likelySource, ph) },
              { label: sm.filterStateLabel ?? "", value: orPh(snap.filterState, ph) },
              { label: sm.capacitorBankLabel ?? "", value: orPh(snap.capacitorBank, ph) },
              {
                label: sm.nextPriorityLabel ?? "", value: orPh(snap.nextPriority, ph),
                valueColor: snap.nextPriorityTone === "critical" ? palette.priorityCritical
                  : snap.nextPriorityTone === "watch" ? palette.priorityWatch : palette.priorityDefault,
              },
            ]}
          />
        </>
      )}
    </Card>
  );
}

// ── cards 48/49 — always-draw normalizers (crash-guards only; blanks stay blank, no seeded points) ─────────────────
const isArr = Array.isArray;
const numOr = (v: any, d: number): number => { const n = fin(v); return n == null ? d : n; };
const blankToDash = (v: any): any => (v == null || v === "" ? "—" : v);
const validSeries = (s: any[]): any[] => (isArr(s) ? s : []).filter((x: any) => x && isArr(x.values));
const numTicks = (t: any[]): number[] => (isArr(t) ? t : []).filter((x: any) => fin(x) != null);
const lineOrUndef = (l: any): any => (l && fin(l.value) != null ? l : undefined);

/** DistortionProfileChart view slice — array-safe series/yTicks, finite axis bounds, honest averageStat/ref-lines. */
function safeProfileSlice(s: any): any {
  const o = s && typeof s === "object" ? s : {};
  return {
    ...o,
    series: validSeries(o.series),
    yTicks: numTicks(o.yTicks),
    yMin: numOr(o.yMin, 0), yMax: numOr(o.yMax, 1),
    yAxisLabel: typeof o.yAxisLabel === "string" ? o.yAxisLabel : "",
    maxLine: lineOrUndef(o.maxLine), minLine: lineOrUndef(o.minLine),
    averageStat: o.averageStat ? { label: String(o.averageStat.label ?? ""), value: dash(o.averageStat.value) } : undefined,
  };
}
function safeProfile(dp: any): any {
  const src = dp && typeof dp === "object" ? dp : {};
  const vsrc = src.views && typeof src.views === "object" ? src.views : {};
  const views: Record<string, any> = {};
  for (const k of Object.keys(vsrc)) views[k] = safeProfileSlice(vsrc[k]);
  let keys = Object.keys(views);
  if (!keys.length) { views.__empty = safeProfileSlice({}); keys = ["__empty"]; }
  return {
    ...src,
    view: views[src.view] ? src.view : keys[0],
    views,
    xLabels: isArr(src.xLabels) ? src.xLabels : [],
    xLabelIndexes: isArr(src.xLabelIndexes) ? src.xLabelIndexes : [],
    viewOptions: isArr(src.viewOptions) ? src.viewOptions : undefined,
  };
}

const normRailRow = (r: any): any => {
  const o = r && typeof r === "object" ? r : {};
  return { ...o, label: String(o.label ?? ""), value: blankToDash(o.value) };
};
/** LoadImpactChart view slice — array-safe series/watchLines/yTicks/xLabels, honest stats/kpis (blank → '—'). */
function safeLoadImpactSlice(s: any): any {
  const o = s && typeof s === "object" ? s : {};
  const railKind = o.railKind === "kpi-grid" ? "kpi-grid" : "stat-list";
  return {
    ...o,
    series: validSeries(o.series),
    watchLines: (isArr(o.watchLines) ? o.watchLines : []).filter((w: any) => w && fin(w.value) != null),
    yTicks: numTicks(o.yTicks),
    xLabels: isArr(o.xLabels) ? o.xLabels : [],
    xLabelIndexes: isArr(o.xLabelIndexes) ? o.xLabelIndexes : [],
    yMin: numOr(o.yMin, 0), yMax: numOr(o.yMax, 1),
    yAxisLabel: typeof o.yAxisLabel === "string" ? o.yAxisLabel : "",
    railKind,
    stats: isArr(o.stats) ? o.stats.map(normRailRow) : railKind === "stat-list" ? [] : undefined,
    kpis: isArr(o.kpis) ? o.kpis.map(normRailRow) : railKind === "kpi-grid" ? [] : undefined,
  };
}
function safeLoadImpact(li: any): any {
  const src = li && typeof li === "object" ? li : {};
  const vsrc = src.views && typeof src.views === "object" ? src.views : {};
  const views: Record<string, any> = {};
  for (const k of Object.keys(vsrc)) views[k] = safeLoadImpactSlice(vsrc[k]);
  let keys = Object.keys(views);
  if (!keys.length) { views.__empty = safeLoadImpactSlice({}); keys = ["__empty"]; }
  return {
    ...src,
    view: views[src.view] ? src.view : keys[0],
    views,
    viewOptions: isArr(src.viewOptions) ? src.viewOptions : undefined,
  };
}

// SamplingPicker committed selection → host date_window (reimplements feeder-power-quality/date-window.ts).
const PRESET_TO_RANGE: Record<string, string> = {
  today: "today", yesterday: "yesterday", "last-7-days": "last-7-days", "this-month": "this-month", "last-month": "this-month",
};
function samplingToDateWindow(sel: SamplingSelection): any {
  const sampling = (sel?.resolution as string | undefined) ?? "2hour";
  if (sel?.preset === "custom") {
    return { range: "custom-range", start: sel.range?.start ?? undefined, end: sel.range?.end ?? undefined, sampling };
  }
  return { range: PRESET_TO_RANGE[sel?.preset] ?? "today", sampling };
}

export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  47: (p) => <Card47 payload={p} />,
  48: (p, onDateChange) => (
    <DistortionProfileChart
      data={safeProfile(p?.distortionProfile) as any}
      className="h-full w-full"
      samplingShowCalendar={false}
      onSamplingChange={(next: SamplingSelection) => onDateChange?.(samplingToDateWindow(next))}
    />
  ),
  49: (p, onDateChange) => (
    <LoadImpactChart
      data={safeLoadImpact(p?.loadImpact) as any}
      className="h-full w-full"
      samplingShowCalendar={false}
      onSamplingChange={(next: SamplingSelection) => onDateChange?.(samplingToDateWindow(next))}
    />
  ),
};
