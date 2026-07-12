// prim/shared.tsx — the GENERIC payload→primitive adapters every family file composes. [primitives-only port]
//
// USER DIRECTIVE (2026-07-12): no page cards — the host mounts CMD_V2 chart PRIMITIVES directly; header, legends,
// colors and values all ride the payload (AI-morphable). Rules of this file: imports ONLY from the primitives barrel;
// series/columns/tiles are looked up from the payload BY KEY (never a closed accessor record); every scalar formats
// through fin()/fmtNum() so an honest-blank leaf renders '—', never a crash; tone/color lookups fall back, never
// record-miss. See docs/primitives_inventory/PORT_CONTRACT.md.
import React from "react";
import {
  AiSummary,
  BodyCard,
  DataTable,
  EventStripControls,
  MetricTileGrid,
  RadarChart,
  SegmentBar,
  resolveEventFilter,
} from "@cmd-v2/components/charts/primitives";
import { selectionToWindow, resampleForPreset } from "./date-wiring";

// ── scalar guards ──────────────────────────────────────────────────────────────────────────────────────────────────
export const fin = (v: any): number | null => {
  const n = Number(v);
  return v == null || v === "" || !Number.isFinite(n) ? null : n;
};
export const dash = (v: any): string => (v == null || v === "" ? "—" : String(v));
export const fmtNum = (v: any, decimals?: number | null, unit?: string | null): string => {
  const n = fin(v);
  if (n == null) return "—";
  const d = decimals == null ? (Math.abs(n) >= 100 ? 0 : 2) : Number(decimals) || 0;
  const s = n.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  return unit ? `${s} ${unit}` : s;
};
/** Dotted-path read ('worstVoltage.vDeviation'). */
export const pathGet = (o: any, path: string): any =>
  String(path).split(".").reduce((acc, k) => (acc == null ? acc : acc[k]), o);

/** `${titlePrefix}${titleConnector}${period.label}` when the pres speaks that pattern, else the first present title. */
export const cardTitle = (pres: any, period?: any, fallback?: string): string => {
  if (pres?.titlePrefix != null) return `${pres.titlePrefix}${pres.titleConnector ?? ""}${period?.label ?? ""}`;
  return String(pres?.cardTitle ?? pres?.title ?? fallback ?? "");
};

// ── AI summary card (BodyCard + AiSummary blocks) ─────────────────────────────────────────────────────────────────
export function PrimAi({ title, blocks, density }:
  { title: string; blocks: Array<{ label?: string; text: string }>; density?: any }) {
  return (
    <BodyCard title={title}>
      <div className="flex flex-col gap-3">
        {blocks.filter((b) => b && b.text).map((b, i) => (
          <div key={i}>
            {b.label ? <div style={{ fontSize: 10, letterSpacing: "0.08em", opacity: 0.6 }}>{b.label}</div> : null}
            <AiSummary text={b.text} density={density} className="mt-1" />
          </div>
        ))}
      </div>
    </BodyCard>
  );
}

// ── metric tile strip (EventStripControls + SegmentBar + MetricTileGrid) ──────────────────────────────────────────
// Tile values read GENERICALLY: statPathByKey[key] (dotted path into stats) wins, else stats[key]. 'representsAll'
// tiles show the total. pct = share of the representsAll total. A dark key renders '—' + disabled — never NaN.
export function PrimTiles({ strip, statPathByKey = {}, onDateChange }:
  { strip: any; statPathByKey?: Record<string, string>; onDateChange?: (dw: any) => void }) {
  const pres = strip?.pres ?? {};
  const stats = strip?.stats ?? {};
  const [selection, setSelection] = React.useState<any>(() => ({
    preset: strip?.filterSelection?.preset ?? "today",
    resample: strip?.filterSelection?.resample ?? "hourly",
    customDate: strip?.filterSelection?.customDate ?? "",
    rangeStart: strip?.filterSelection?.rangeStart ?? "",
    rangeEnd: strip?.filterSelection?.rangeEnd ?? "",
  }));
  const [selectedTileKey, setSelectedTileKey] = React.useState<string | null>(null);
  const fire = (next: any) => {
    setSelection(next);
    try { onDateChange && onDateChange(selectionToWindow(next)); } catch { /* window stays */ }
  };
  const valueOf = (key: string): number | null =>
    fin(statPathByKey[key] != null ? pathGet(stats, statPathByKey[key]) : stats?.[key]);
  const totalKey = (pres.tiles ?? []).find((t: any) => t?.representsAll)?.key;
  const total = totalKey != null ? valueOf(totalKey) : fin(stats?.total);
  const tileByKey = new Map((pres.tiles ?? []).map((t: any) => [t?.key, t]));
  const tiles = (pres.tileOrder ?? []).flatMap((key: string) => {
    const t: any = tileByKey.get(key);
    if (!t) return [];
    const v = valueOf(key);
    const isCount = !t.unit && !t.representsAll;
    return [{
      key: t.key, label: t.label, swatch: t.swatch ?? "none", color: t.color,
      payload: t.payload ?? null, representsAll: !!t.representsAll,
      displayValue: fmtNum(v, t.decimals, t.unit),
      pct: t.representsAll ? (v != null && v > 0 ? 100 : null)
        : (isCount && v != null && total != null && total > 0 ? Math.round((v / total) * 100) : null),
      disabled: v == null || v === 0,
    }];
  });
  const segByKey = new Map((pres.segments ?? []).map((s: any) => [s?.key, s]));
  const segments = (pres.segmentOrder ?? []).flatMap((key: string) => {
    const s: any = segByKey.get(key);
    const v = valueOf(key);
    return s && v != null ? [{ key, value: v, color: s.color }] : [];
  });
  const c = pres.controls ?? {};
  return (
    <div className="flex flex-col">
      <EventStripControls
        preset={selection.preset} resample={selection.resample}
        resolvedFilter={resolveEventFilter(selection)}
        timeChoice={strip?.timeChoice ?? ""} timeOptions={strip?.timeOptions ?? []}
        customDate={selection.customDate} rangeStart={selection.rangeStart} rangeEnd={selection.rangeEnd}
        leadingLabel={pres.controlsLeadingLabel}
        presetOptions={c.presetOptions} resampleOptions={c.resampleOptions}
        labels={{ to: c.toLabel, by: c.byLabel, at: c.atLabel }}
        onPresetChange={(p: any) => fire({ ...selection, preset: p, resample: resampleForPreset(p) })}
        onResampleChange={(r: any) => fire({ ...selection, resample: r })}
        onTimeChange={() => undefined}
        onCustomDateChange={(v: string) => fire({ ...selection, customDate: v })}
        onRangeStartChange={(v: string) => fire({ ...selection, rangeStart: v })}
        onRangeEndChange={(v: string) => fire({ ...selection, rangeEnd: v })}
      />
      {segments.length ? <SegmentBar segments={segments} className="mt-2" /> : null}
      <MetricTileGrid tiles={tiles} selectedTileKey={selectedTileKey}
        onTileSelect={(k: string | null) => setSelectedTileKey(k)} />
    </div>
  );
}

// ── data table (BodyCard + DataTable, columns fully payload-driven) ───────────────────────────────────────────────
// A column's cell reads row[col.field ?? fieldAliases[col.id] ?? col.id] — the payload (or a family DATA alias map)
// owns the binding, never a switch. 'events'-style expansion: a columnOrder id of `eventsKey` expands to one column
// per pres[modeOrderKey] entry rendering row[mode] (the payload-keyed loophole made first-class).
export function PrimTable({ sub, fieldAliases = {}, title }:
  { sub: any; fieldAliases?: Record<string, string>; title?: string }) {
  const pres = sub?.pres ?? {};
  const rows = (sub?.period?.panels ?? sub?.rows ?? []).filter((r: any) => r && typeof r === "object");
  const [selected, setSelected] = React.useState<string | null>(sub?.selectedPanelId ?? null);
  const colByKey = new Map((pres.columns ?? []).map((c: any) => [c?.id, c]));
  const cellText = (row: any, col: any) => {
    const field = col.field ?? fieldAliases[col.id] ?? col.id;
    const v = row?.[field];
    const n = fin(v);
    if (n != null) return fmtNum(n, col.decimals, col.percentUnit ? "%" : col.header?.unit);
    return dash(v);
  };
  const columns = (pres.columnOrder ?? []).flatMap((id: string) => {
    if (id === "events" && Array.isArray(pres.eventModeOrder)) {
      const modes = sub?.mode ? [sub.mode] : pres.eventModeOrder;
      return modes.map((m: string) => ({
        id: `event-${m}`,
        header: `${pres.eventColumn?.shortByMode?.[m] ?? m} ${pres.eventColumn?.descriptor ?? ""}`.trim(),
        align: pres.eventColumn?.align,
        render: (row: any) => dash(row?.[m]),
      }));
    }
    const col: any = colByKey.get(id);
    if (!col) return [];
    return [{
      id, header: col.header?.label ?? col.header ?? id, align: col.align,
      fit: col.fit, render: (row: any) => cellText(row, col),
    }];
  });
  return (
    <BodyCard title={title ?? cardTitle(pres, sub?.period)}>
      <DataTable
        ariaLabel={pres.ariaLabel}
        columns={columns} rows={rows}
        getRowKey={(row: any, i: number) => String(row?.id ?? i)}
        selectedRowKey={selected}
        onRowClick={(row: any) => setSelected(String(row?.id ?? ""))}
        fillHeight minWidth={sub?.mode ? pres.singleModeMinWidth : pres.minWidth}
        headerHeight={pres.layout?.headerHeight} rowHeight={pres.layout?.rowHeight}
        maxRowHeight={pres.layout?.maxRowHeight}
      />
    </BodyCard>
  );
}

// ── radar (RadarChart + payload-chromed rail; sections → the comparison radar in section-split) ───────────────────
export function PrimRadar({ distribution }: { distribution: any }) {
  const pres = distribution?.pres ?? {};
  const period = distribution?.period ?? {};
  const rows = (Array.isArray(period.panels) ? period.panels : [])
    .filter((r: any) => r && fin(r.amps) != null && r.role !== "incoming");
  const repl = Array.isArray(pres.spokeLabelReplacements) ? pres.spokeLabelReplacements : [];
  const label = (s: any) => repl.reduce(
    (acc: string, r: any) => (r && typeof r.from === "string" ? acc.split(r.from).join(r.to ?? "") : acc),
    String(s ?? ""));
  const spokes = rows.map((r: any) => ({ id: String(r.id ?? r.panel), label: label(r.panel ?? r.id), value: fin(r.amps) ?? 0 }));
  const values = spokes.map((s: any) => s.value);
  const total = values.reduce((a: number, b: number) => a + b, 0);
  const average = values.length ? total / values.length : null;
  const peak = values.length ? Math.max(...values) : null;
  const valueByKey: Record<string, number | null> = { total, average, peak };
  const railRows = (pres.railOrder ?? []).flatMap((key: string) => {
    const row = (pres.rail ?? []).find((r: any) => r?.key === key);
    return row ? [{ ...row, value: valueByKey[key] ?? null }] : [];
  });
  const radar = pres.radar ?? {};
  return (
    <BodyCard title={cardTitle(pres, period)}>
      <div className="flex h-full min-h-0 gap-4">
        <div className="min-w-0 flex-1">
          <RadarChart spokes={spokes} selectedId={distribution?.selectedPanelId ?? undefined}
            referenceValue={average} referenceFill={radar.referenceFill} referenceStroke={radar.referenceStroke}
            polygonFill={radar.polygonFill} polygonStroke={radar.polygonStroke} showPeakDot={!!radar.showPeakDot} />
        </div>
        <div className="flex w-36 shrink-0 flex-col justify-center gap-3 border-l pl-4">
          {railRows.map((r: any) => (
            <div key={r.key}>
              <div className="flex items-center gap-2" style={{ fontSize: 12, opacity: 0.75 }}>
                <span style={{ width: 10, height: 10, background: r.color, borderRadius: r.dot ? 999 : 2, display: "inline-block" }} />
                {r.label}
              </div>
              <div style={{ fontSize: 20, fontWeight: 600 }}>
                {fmtNum(r.value, pres.railDecimals, pres.unit)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </BodyCard>
  );
}
