// prim/vc-events.tsx — Voltage & Current tab (cards 18-22) on PRIMITIVES ONLY. [primitives-only port]
//
// Every card mounts CMD_V2 chart primitives directly from its completed payload; header/legends/colors/values ride
// the payload (AI-morphable). The timeline uses the key-generic EventTimelineSections view (accessor = p[key], so
// section-split variant keys AND the canonical sag/swell/current/neutral keys both render); the radar picks the
// comparison radar on a sectionCompare payload; the table's columns are the payload's own pres roster.
import React from "react";
import { PrimAi, PrimRadar, PrimTable, PrimTiles, cardTitle, dash } from "./shared";
import { EventTimelineSections, SectionRadar } from "../section-split";

// legacy pres column ids whose row FIELD differs (DATA, not a switch — the payload's own `field` always wins)
const VC_TABLE_FIELDS: Record<string, string> = { voltage: "vAvg" };
// worst-of tiles read argmax ROWS — dotted stat paths (DATA; a payload `stat` path would win if present)
const VC_TILE_STATS: Record<string, string> = { vDev: "worstVoltage.vDeviation", iImb: "worstCurrent.iUnbalance" };

function Card19({ summary, ai }: { summary: any; ai: any }) {
  const pres = summary?.pres ?? {};
  const text = String(ai?.text ?? pres.backendHeadline ?? "");
  const worst = summary?.stats?.worstCurrent?.panel || summary?.stats?.worstVoltage?.panel;
  const drivers = text && worst
    ? `${pres.vocab?.driversPrefix ?? ""}${worst}${pres.vocab?.driversSuffix ?? ""}` : "";
  return (
    <PrimAi title={cardTitle(pres, summary?.period, "AI Summary")} density={pres.density}
      blocks={[{ label: pres.aiLabel, text: dash(text) },
               ...(drivers ? [{ label: pres.driversLabel, text: drivers }] : [])]} />
  );
}

export const CARDS: Record<number, (p: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  18: (p, onDateChange) => <PrimTiles strip={p?.strip} statPathByKey={VC_TILE_STATS} onDateChange={onDateChange} />,
  19: (p) => <Card19 summary={p?.summary} ai={p?.ai_summary ?? p?.widgets?.ai_summary} />,
  20: (p) => (
    <div className="h-full">
      <EventTimelineSections
        pres={p?.trend?.pres ?? {}} period={p?.trend?.period ?? { label: "" }}
        points={Array.isArray(p?.trend?.points) ? p.trend.points : []}
        selectedLabel={p?.trend?.selectedLabel ?? ""} selectedTileKey={p?.trend?.selectedTileKey ?? null}
        onPeriodSelect={() => undefined} />
    </div>
  ),
  21: (p) => (
    <div className="h-full">
      {Array.isArray(p?.distribution?.sectionCompare) && p.distribution.sectionCompare.length >= 2
        && (p?.distribution?.period?.panels ?? []).length > 0
        ? <SectionRadar distribution={p.distribution} />
        : <PrimRadar distribution={p?.distribution} />}
    </div>
  ),
  22: (p) => <PrimTable sub={p?.table} fieldAliases={VC_TABLE_FIELDS} />,
};
