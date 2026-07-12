// prim/hh-health.tsx — HealthSummaryPanel-class (cards 43/45 feeder, 66/68 DG) on PRIMITIVES ONLY. [port]
//
// Faithful reimplementation of CMD_V2 pages/electrical/tabs/voltage-current/HealthSummaryPanel — barrel imports
// only (the original imported the same primitives + a type-only ./types). Header title + StatusBadge/StatusPill,
// a summary headline + a 25/50/25 DeviationBand (marker rides band.markerPct), a KpiStatStrip of data.metrics,
// and per-phase rows (PhaseValueRows 'rows' or local FillBar-style balance bars 'bars'), then an insight footer.
// Honesty: STATUS_PILL_BY_TONE / DELTA_TONE lookups fall back to nothing (never a record-miss crash); a non-finite
// band marker hides the marker+label (no phantom reading); blank scalars render '—'.
import type { CSSProperties } from "react";
import {
  Card,
  CardBodySkeleton,
  CHART_COLORS,
  composeMetricText,
  composeValueUnit,
  KpiStatStrip,
  PhaseValueRows,
  PRESENTATION_LABELS,
  StatusBadge,
  StatusPill,
  SURFACES,
  TYPOGRAPHY,
  TYPOGRAPHY_FAMILY,
} from "@cmd-v2/components/charts/primitives";

// Pill CHROME resolved from the semantic tone — a design-system choice, DERIVED not payload; an unknown tone
// (the honest-blank '' / 'neutral') falls outside the record → statusPill undefined → no pill (safe fallback).
const STATUS_PILL_BY_TONE: Record<string, { tone: "normal" | "watch"; leading: "dot" | "glyph"; glyph: string }> = {
  normal: { tone: "normal", leading: "dot", glyph: "▲" },
  warning: { tone: "watch", leading: "glyph", glyph: "▲" },
};
// Deviation-delta color by tone; unknown tone (blank '—') → undefined color (no crash, inherits).
const DELTA_TONE: Record<string, string> = {
  good: CHART_COLORS.sage700,
  bad: CHART_COLORS.coral500,
  neutral: CHART_COLORS.sky600,
};

const dash = (v: any): string => (v == null || v === "" ? "—" : String(v));
const finite = (v: any): number | null => {
  const n = Number(v);
  return v == null || v === "" || !Number.isFinite(n) ? null : n;
};
const clampPct = (v: any): number => Math.max(0, Math.min(100, Number(v) || 0));

const HEALTH_CARD_STYLE: CSSProperties = { borderRadius: 10, padding: 10 };
const HEADER_STYLE: CSSProperties = { borderBottom: `1px ${SURFACES.divider.style} ${SURFACES.divider.color}`, paddingBottom: 6 };
const TITLE_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 14, fontWeight: 400, color: CHART_COLORS.teal950, lineHeight: "21px", letterSpacing: 0 };
const SUMMARY_VALUE_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 26, fontWeight: 700, color: CHART_COLORS.teal990, lineHeight: "1.1", letterSpacing: 0 };
const SUMMARY_UNIT_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.plex, fontSize: 13, fontWeight: 400, color: CHART_COLORS.sky600, lineHeight: "normal" };
const CAPTION_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.plex, fontSize: 12, fontWeight: 400, color: CHART_COLORS.tealLabel600, lineHeight: "normal" };
const DEVIATION_LABEL_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 11, fontWeight: 700, color: CHART_COLORS.sage800, lineHeight: "normal", letterSpacing: 0 };
const TICK_LABEL_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.plex, fontSize: 10, fontWeight: 400, color: CHART_COLORS.sky600, lineHeight: "normal" };
const INSIGHT_STYLE: CSSProperties = { ...TYPOGRAPHY.insightText, color: CHART_COLORS.tealLabel600 };
const PHASE_BAR_LABEL_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 13, fontWeight: 700, color: CHART_COLORS.teal900, lineHeight: "18px", letterSpacing: 0 };
const PHASE_BAR_VALUE_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 13, fontWeight: 400, color: CHART_COLORS.teal900, lineHeight: "18px", letterSpacing: 0 };
const PHASE_BAR_DELTA_STYLE: CSSProperties = { fontFamily: TYPOGRAPHY_FAMILY.spaceMono, fontSize: 12, fontWeight: 700, lineHeight: "18px", letterSpacing: 0 };

function summaryCaption(summary: any): string {
  if (summary.caption) return summary.caption;
  const nominal = [summary.nominal, summary.nominalUnit].filter(Boolean).join(" ");
  const nominalWord = summary.nominalLabel ?? PRESENTATION_LABELS.nominal;
  return nominal ? `${summary.label} · ${nominalWord} ${nominal}` : dash(summary.label);
}
function formatDeviationLabel(summary: any): string {
  if (summary.deviation == null || summary.deviation === "" || summary.deviation === "—") return "—";
  return composeValueUnit(String(summary.deviation), summary.deviationUnit ?? "", "");
}

function HealthSummary({ summary, hasBand }: { summary: any; hasBand: boolean }) {
  const sideText = [summary.sideValue, summary.sideUnit].filter((v) => v != null && v !== "").join(" ");
  return (
    <div className={`${hasBand ? "mb-2" : "mb-0"} flex min-w-0 items-end justify-between gap-3`}>
      <div className="min-w-0">
        <div className="flex min-w-0 items-baseline gap-1">
          <span className="truncate" style={SUMMARY_VALUE_STYLE}>{dash(summary.value)}</span>
          <span style={SUMMARY_UNIT_STYLE}>{summary.unit}</span>
        </div>
        <p className="mt-1 truncate" style={CAPTION_STYLE}>{summaryCaption(summary)}</p>
      </div>
      {summary.sideLabel || sideText ? (
        <div className="flex shrink-0 items-baseline justify-end gap-1 whitespace-nowrap">
          {summary.sideLabel ? <span style={CAPTION_STYLE}>{summary.sideLabel}</span> : null}
          {sideText ? (
            <span style={{ fontFamily: TYPOGRAPHY_FAMILY.plex, fontSize: 13, fontWeight: 600, color: CHART_COLORS.teal990, lineHeight: "20.8px" }}>{sideText}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function DeviationBand({ band, deviationLabel }: { band: any; deviationLabel: string }) {
  const markerN = finite(band.markerPct); // non-finite (honest-blank '—') → no marker, no phantom reading
  const markerLeft = markerN != null ? `clamp(16px, ${markerN}%, calc(100% - 16px))` : undefined;
  const labels: any[] = Array.isArray(band.labels) ? band.labels : [];
  return (
    <div className="w-full">
      <div className="relative h-[27px]">
        {markerN != null ? (
          <span className="absolute top-0 -translate-x-1/2 whitespace-nowrap" style={{ ...DEVIATION_LABEL_STYLE, left: markerLeft }}>{deviationLabel}</span>
        ) : null}
        <div className="absolute bottom-0 left-0 flex h-2 w-full overflow-hidden rounded-[4px]" style={{ background: CHART_COLORS.cream200 }}>
          <span className="basis-1/4" style={{ background: CHART_COLORS.voltageHealthBandDanger }} />
          <span className="basis-1/2" style={{ background: CHART_COLORS.voltageHealthBandNormal }} />
          <span className="basis-1/4" style={{ background: CHART_COLORS.voltageHealthBandDanger }} />
        </div>
        {markerN != null ? (
          <span className="absolute bottom-[-4px] h-4 w-[10px] -translate-x-1/2 rounded-[8px] border-2 shadow-sm" style={{ left: markerLeft, background: CHART_COLORS.teal900, borderColor: CHART_COLORS.cream100 }} />
        ) : null}
      </div>
      <div className="mt-1 flex justify-between" style={TICK_LABEL_STYLE}>
        {labels.map((label, i) => {
          const text = typeof label === "string" ? label : label && typeof label === "object" ? composeMetricText(label) : dash(label);
          return <span key={`${text}-${i}`}>{text}</span>;
        })}
      </div>
    </div>
  );
}

function MetricStrip({ metrics, hasSummary }: { metrics: any[]; hasSummary: boolean }) {
  return (
    <KpiStatStrip
      className={hasSummary ? "mt-2" : ""}
      height="auto"
      withBottomDivider
      withCellDividers={false}
      cells={metrics.map((m: any, i: number) => ({
        id: `${m.label ?? "m"}-${i}`,
        label: m.label,
        value: dash(m.value),
        unit: m.unit,
        sub: m.note,
        valueColor: m.tone === "warning" ? CHART_COLORS.warning600 : undefined,
        unitColor: m.tone === "warning" ? CHART_COLORS.warning600 : undefined,
      }))}
    />
  );
}

function PhaseBarRows({ phases, className }: { phases: any[]; className?: string }) {
  return (
    <div className={["flex min-w-0 flex-col gap-[7px]", className ?? ""].join(" ").trim()}>
      {phases.map((phase: any, i: number) => (
        <div key={`${phase.label}-${i}`} className="grid min-w-0 items-center gap-2" style={{ gridTemplateColumns: "minmax(46px, auto) minmax(0, 1fr) max-content max-content", height: 18 }}>
          <span className="whitespace-nowrap" style={PHASE_BAR_LABEL_STYLE}>{phase.label}</span>
          <div className="relative h-[6px] w-full overflow-hidden rounded-[3px]" style={{ background: CHART_COLORS.cream200 }}>
            <div className="absolute inset-y-0 left-0 rounded-[3px]" style={{ width: `${clampPct(phase.widthPct)}%`, background: phase.color }} />
            {finite(phase.markerPct) != null ? (
              <span className="absolute top-[-2px] bottom-[-2px] w-[2px] -translate-x-1/2 rounded-[1px]" style={{ left: `${clampPct(phase.markerPct)}%`, background: CHART_COLORS.teal900 }} />
            ) : null}
          </div>
          <span className="whitespace-nowrap text-right tabular-nums" style={PHASE_BAR_VALUE_STYLE}>{composeValueUnit(dash(phase.value), phase.unit)}</span>
          <span className="min-w-[38px] whitespace-nowrap text-right tabular-nums" style={{ ...PHASE_BAR_DELTA_STYLE, color: DELTA_TONE[phase.deltaTone] }}>
            {phase.deltaText && typeof phase.deltaText === "object" ? composeMetricText(phase.deltaText) : dash(phase.delta)}
          </span>
        </div>
      ))}
    </div>
  );
}

function PhaseRows({ phases, hasSummary, variant }: { phases: any[]; hasSummary: boolean; variant: "rows" | "bars" }) {
  const marginClass = hasSummary ? "mt-2" : "mt-4";
  if (variant === "bars") return <PhaseBarRows phases={phases} className={marginClass} />;
  return (
    <PhaseValueRows
      className={marginClass}
      rowHeight={22}
      rows={phases.map((phase: any, i: number) => ({
        id: `${phase.label}-${i}`,
        label: phase.label,
        color: phase.color,
        value: composeValueUnit(dash(phase.value), phase.unit),
      }))}
    />
  );
}

/** HealthCard — cards 43/45 (feeder) + 66/68 (DG). `data` = HealthCardData; `phaseVariant` selects rows|bars. */
export function HealthCard({ data, phaseVariant = "rows", loading = false }: { data: any; phaseVariant?: "rows" | "bars"; loading?: boolean }) {
  const d = data ?? {};
  const status = d.status ?? null;
  const statusPill = status ? STATUS_PILL_BY_TONE[status.tone] : null;
  const statusLabel = d.statusVocab && status?.statusKey != null ? d.statusVocab[status.statusKey] ?? status.label : status?.label;
  const insightText = d.insightVocab && d.insightKey != null ? d.insightVocab[d.insightKey] ?? d.insight : d.insight;
  const hasSummary = Boolean(d.summary);
  const metrics: any[] = Array.isArray(d.metrics) ? d.metrics : [];
  const phases: any[] = Array.isArray(d.phases) ? d.phases : [];

  return (
    <Card className="h-full" overflow="auto" style={HEALTH_CARD_STYLE}>
      <header className="flex shrink-0 items-center justify-between gap-3" style={HEADER_STYLE}>
        <h3 className="min-w-0 truncate" style={TITLE_STYLE}>{dash(d.title)}</h3>
        <div className="flex shrink-0 items-center gap-2">
          {d.staleBadge ? <StatusBadge label={d.staleBadge.label} tone={d.staleBadge.tone} /> : null}
          {status && statusPill ? (
            <StatusPill label={statusLabel ?? status.label} tone={statusPill.tone} leading={statusPill.leading} glyph={statusPill.glyph} />
          ) : null}
        </div>
      </header>

      {loading ? (
        <CardBodySkeleton kpiCells={3} className="pt-2" />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col justify-between gap-2 pt-2">
          <div className="min-w-0">
            {d.summary ? (
              <div className="border-b pb-2" style={{ borderColor: SURFACES.divider.color, borderStyle: SURFACES.divider.style }}>
                <HealthSummary summary={d.summary} hasBand={Boolean(d.band)} />
                {d.band ? <DeviationBand band={d.band} deviationLabel={formatDeviationLabel(d.summary)} /> : null}
              </div>
            ) : null}
            <MetricStrip metrics={metrics} hasSummary={hasSummary} />
            <PhaseRows phases={phases} hasSummary={hasSummary} variant={phaseVariant} />
          </div>
          <p className="mt-2 min-w-0 shrink-0 border-t pt-2" style={{ ...INSIGHT_STYLE, fontSize: 12, lineHeight: 1.45, borderColor: SURFACES.divider.color, borderStyle: SURFACES.divider.style }}>
            {insightText ?? d.insight ?? ""}
          </p>
        </div>
      )}
    </Card>
  );
}
