// prim/pq.tsx — Harmonics & PQ tab (cards 23-27) on PRIMITIVES ONLY. [primitives-only port]
//
// Every card mounts a CMD_V2 chart primitive directly from its completed payload; header/legends/colors/values ride
// the payload (AI-morphable). 23 strip → shared PrimTiles (EventStripControls + SegmentBar + MetricTileGrid), 24
// timeline → the key-generic EventTimelineSections view (its counts are DERIVED per-bucket like the page card's
// periodStats), 25 AI → shared PrimAi, 26 feeder table → DataTable with a per-column formatter, 27 signature →
// ComparisonRadarChart (API positional-generic, else the mock six-field spoke order).
import React from "react";
import { BodyCard, ComparisonRadarChart, DataTable } from "@cmd-v2/components/charts/primitives";
import { PrimAi, PrimTiles, cardTitle, dash, fmtNum } from "./shared";
import { EventTimelineSections } from "../section-split";

// Worst-of strip tiles read an argmax ROW off a dotted stats path (DATA, not a switch — a payload `stat` path wins).
const PQ_TILE_STATS: Record<string, string> = { worstI: "worstIThd.iThd", worstV: "worstVThd.vThd" };
// Feeder-table column id → row FIELD where they differ (only PF: legacy id `pf` reads row `truePf`); the rest id===field.
const PQ_TABLE_FIELDS: Record<string, string> = { pf: "truePf" };
// Which FocusKey each overlay line dims with (worstI↔iThd, worstV↔vThd) — the page card's lineFocusOf, made explicit
// on the pres so the key-generic sections view can dim the correct line (card 24 lineSeries carry no tileKey).
const PQ_LINE_TILE: Record<string, string> = { worstI: "iThd", worstV: "vThd" };
// Mock-mode signature spoke order — FIXED to the six harmonic fields (API mode is positional-generic instead).
const SIG_FIELDS = ["h3", "h5", "h7", "iThd", "vThd", "kFactor"];

// Coerce a leaf to a finite number, matching the JS `>`/`<` semantics of the page card's periodStats after guarding
// ('—' → NaN → 0, null → 0). Keeps count/worst math byte-identical to CMD_V2's periodStats.
const numOr0 = (v: any): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};
const avg = (vals: number[]): number => (vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0);
// First-occurrence replacement chain (page card uses String.replace, NOT split/join — faithful to its label rewrite).
const applyRepl = (s: any, repls: any[]): string =>
  (Array.isArray(repls) ? repls : []).reduce(
    (acc: string, r: any) => (r && typeof r.from === "string" ? acc.replace(r.from, r.to ?? "") : acc),
    String(s ?? ""));
// Driver phrase → short code (H5/V/PF/N …) via the payload's own code map; unknown → the payload fallback ('—'/OK).
const shortDriver = (driver: any, codeMap: any[], fallback: any): string => {
  const s = driver == null ? "" : String(driver);
  for (const c of Array.isArray(codeMap) ? codeMap : []) {
    if (c && typeof c.match === "string" && s.includes(c.match)) return String(c.code);
  }
  return String(fallback ?? "—");
};

// ── card 24 timeline: DERIVE per-bucket points (page card periodStats) ────────────────────────────────────────────
// The payload carries `periods: PQPeriod[]` (+ a threshold `limits` block), not baked points — the page card counts
// per bucket in-card. Counts ride the payload's OWN limits: a null/absent limit collapses to 0 exactly like CMD_V2's
// `p.iThd > limits.iThdLimit` (JS null→0), so the render is byte-identical to the legacy fill (owners: a null PQ-limit
// block makes every positive feeder count as an "event" — an upstream data gap, not a fabrication of this adapter).
function pqPoint(period: any, limits: any): any {
  const label = String(period?.label ?? "");
  if (period?.precomputedStats) {
    const s = period.precomputedStats;
    return { label, iThd: numOr0(s.iThd), vThd: numOr0(s.vThd), pfGap: numOr0(s.pfGap), neutral: numOr0(s.neutral),
             worstI: numOr0(s.worstIThd?.iThd), worstV: numOr0(s.worstVThd?.vThd) };
  }
  const panels: any[] = Array.isArray(period?.panels) ? period.panels : [];
  const above = (field: string, lim: any) => panels.filter((p) => Number(p?.[field]) > Number(lim)).length;
  const worst = (field: string) => panels.reduce((m: number, p: any) => Math.max(m, numOr0(p?.[field])), 0);
  return {
    label,
    iThd: above("iThd", limits?.iThdLimit),
    vThd: above("vThd", limits?.vThdLimit),
    pfGap: panels.filter((p) => p?.truePf != null && Number(p.truePf) < Number(limits?.truePfFloor)).length,
    neutral: above("neutralA", limits?.neutralLimitA),
    worstI: worst("iThd"),
    worstV: worst("vThd"),
  };
}

function PqTimeline({ timeline }: { timeline: any }) {
  const t = timeline ?? {};
  const pres0 = t.pres ?? {};
  const limits = t.limits ?? {};
  const periods: any[] = Array.isArray(t.periods) ? t.periods : [];
  const points = periods.map((per) => pqPoint(per, limits));
  const lastLabel = points.length ? points[points.length - 1].label : "";
  // The sections view titles as `${titlePrefix}${titleConnector}${period.label}`; the PQ timeline titles with a STATIC
  // `cardTitle` instead — route cardTitle through titlePrefix so the header prints right. A real section-split payload
  // (already carrying titlePrefix) passes through untouched, keeping its live period suffix.
  const hasPrefix = pres0.titlePrefix != null;
  const lineSeries = (Array.isArray(pres0.lineSeries) ? pres0.lineSeries : [])
    .map((s: any) => (s?.tileKey != null ? s : { ...s, tileKey: PQ_LINE_TILE[s?.key] }));
  const pres = hasPrefix
    ? { ...pres0, lineSeries }
    : { ...pres0, lineSeries, titlePrefix: pres0.cardTitle ?? "", titleConnector: "" };
  const period = { label: hasPrefix ? lastLabel : "" };
  return (
    <div className="h-full">
      <EventTimelineSections
        pres={pres} period={period} points={points}
        selectedLabel={t.selectedLabel ?? ""} selectedTileKey={t.focus ?? null}
        onPeriodSelect={() => undefined} />
    </div>
  );
}

// ── card 26 feeder table: DataTable with per-column formatters (units/decimals/driver-code/label rewrite) ──────────
function pqFeederColumns(pres: any): any[] {
  const colByKey = new Map((Array.isArray(pres.columns) ? pres.columns : []).map((c: any) => [c?.id, c]));
  const dec = pres.decimals ?? {};
  const pfDec = (v: any) => (Number(v) < Number(pres.pfDecimalThreshold) ? dec.pfLow : dec.pfHigh);
  const order: string[] = Array.isArray(pres.columnOrder) ? pres.columnOrder : [];
  return order.flatMap((id) => {
    const c: any = colByKey.get(id);
    if (!c) return [];
    const base = { id, header: c.header ?? id, align: c.align,
      ...(c.fit ? { fit: c.fit.fit, fitMin: c.fit.fitMin, fitMax: c.fit.fitMax } : {}) };
    if (id === "panel") return [{ ...base, render: (r: any) => applyRepl(r?.panel, pres.panelLabelReplacements) }];
    if (id === "pf") return [{ ...base, render: (r: any) => (r?.truePf == null ? "—" : fmtNum(r.truePf, pfDec(r.truePf))) }];
    if (id === "driver") return [{ ...base, render: (r: any) => shortDriver(r?.driver, pres.driverCodeMap, pres.driverFallbackCode) }];
    const field = PQ_TABLE_FIELDS[id] ?? id;
    return [{ ...base, render: (r: any) => fmtNum(r?.[field], dec.thd, c.unit) }];
  });
}

function PqFeederTable({ table }: { table: any }) {
  const pres = table?.pres ?? {};
  const period = table?.period ?? {};
  const rows = (Array.isArray(period.panels) ? period.panels : []).filter((r: any) => r && typeof r === "object");
  const [selected, setSelected] = React.useState<string | null>(table?.selectedPanelId ?? null);
  const pal = pres.palette ?? {};
  const layout = pres.layout ?? {};
  return (
    <BodyCard title={cardTitle(pres, period)}>
      <DataTable
        ariaLabel={pres.ariaLabel}
        columns={pqFeederColumns(pres)} rows={rows}
        getRowKey={(r: any, i: number) => String(r?.id ?? i)}
        selectedRowKey={selected ?? undefined}
        onRowClick={(r: any) => setSelected(String(r?.id ?? ""))}
        fillHeight scrollBody stickyHeader stickyFirstColumn
        headerHeight={layout.headerHeight} rowHeight={layout.rowHeight} maxRowHeight={layout.maxRowHeight}
        hoverStyle={pal.rowHoverBg ? { background: pal.rowHoverBg } : undefined}
        selectedStyle={{ color: pal.rowSelectedText, background: pal.rowSelectedBg,
          outline: pal.rowSelectedBorder ? `1px solid ${pal.rowSelectedBorder}` : undefined,
          outlineOffset: -1, borderRadius: 4 }}
      />
    </BodyCard>
  );
}

// ── card 27 signature: ComparisonRadarChart (selected vs fleet) ───────────────────────────────────────────────────
function PqSignature({ signature }: { signature: any }) {
  const pres = signature?.pres ?? {};
  const period = signature?.period ?? {};
  const panels: any[] = Array.isArray(period.panels) ? period.panels : [];
  const spokes = (Array.isArray(pres.spokes) ? pres.spokes : []).map((s: any) => String(s));
  const selected = panels.find((p) => String(p?.id) === String(signature?.selectedPanelId)) ?? panels[0];
  const api = signature?.apiSignature;
  const pal = pres.palette ?? {};
  const st = pres.style ?? {};
  const selColor = pal.selectedColor ?? "#7a4e13";
  const fleetColor = pal.fleetColor ?? "#4A6FA5";
  let series: any[] = [];
  if (api && Array.isArray(api.selectedValues)) {
    // API mode — positional value arrays against pres.spokes (roster-generic).
    series = [
      { key: "selected", name: String(pres.selectedName ?? "Selected"), color: selColor,
        values: api.selectedValues.map(numOr0), strokeWidth: st.selectedStrokeWidth ?? undefined },
      { key: "fleet", name: String(pres.fleetName ?? "Fleet Average"), color: fleetColor,
        values: (Array.isArray(api.fleetAvgValues) ? api.fleetAvgValues : []).map(numOr0),
        strokeWidth: st.fleetStrokeWidth ?? undefined, fillOpacity: st.fleetFillOpacity ?? undefined },
    ];
  } else if (selected && spokes.length > 0) {
    // Mock mode — fixed six-field spoke order; missing harmonic fields are honest gaps (0 on the axis). Empty spokes
    // (this run) → no series → empty radar chrome, never a fabricated flat-zero signature.
    series = [
      { key: "selected", name: String(pres.selectedName ?? "Selected"), color: selColor,
        values: SIG_FIELDS.map((f) => numOr0(selected[f])), strokeWidth: st.selectedStrokeWidth ?? undefined },
      { key: "fleet", name: String(pres.fleetName ?? "Fleet Average"), color: fleetColor,
        values: SIG_FIELDS.map((f) => avg(panels.map((p) => numOr0(p?.[f])))),
        strokeWidth: st.fleetStrokeWidth ?? undefined, fillOpacity: st.fleetFillOpacity ?? undefined },
    ];
  }
  return (
    <BodyCard title={cardTitle(pres, period)}>
      <div className="h-full min-h-0">
        <ComparisonRadarChart spokes={spokes} series={series} margin={{ left: 30 }} />
      </div>
    </BodyCard>
  );
}

function PqAiSummary({ payload }: { payload: any }) {
  const s = payload?.summary ?? {};
  const pres = s.pres ?? {};
  const text = payload?.ai_summary?.text ?? payload?.widgets?.ai_summary?.text ?? pres.backendHeadline;
  return (
    <PrimAi title={cardTitle(pres, s.period, "AI Summary")} density={pres.density}
      blocks={[{ label: pres.badgeLabel, text: dash(text) }]} />
  );
}

export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  23: (p, onDateChange) => <PrimTiles strip={p?.strip} statPathByKey={PQ_TILE_STATS} onDateChange={onDateChange} />,
  24: (p) => <PqTimeline timeline={p?.timeline} />,
  25: (p) => <PqAiSummary payload={p} />,
  26: (p) => <PqFeederTable table={p?.table} />,
  27: (p) => <PqSignature signature={p?.signature} />,
};
