import React from "react";
// Card 43 · Voltage Health Summary (equipment-detail CMD V2 page).
//
// PAYLOAD-DIRECT (ems_backend RETIRED — `frame` is always empty now). Priority:
// payload skeleton → HONEST-EMPTY card. HealthSummaryPanel maps data.metrics + data.phases;
// if the payload elided those leaves, fall back to a STRUCTURE-PRESERVING honest-empty card
// (honestEmptyHealth — payload chrome + empty metrics/phases) so the panel still renders —
// NEVER null, NEVER a source:'mock' seed generator. The old live column-row frame branch
// (ColumnRowState → mapVoltageCurrentSocketToSnapshot → createVoltageCurrentViewModel) is
// dead code now (no frame ever arrives) and was DELETED.

import { HealthSummaryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import type { HealthCardData } from "@cmd-v2/pages/electrical/tabs/voltage-current/types";

/** HONEST-EMPTY draw guarantee [card-43 mock-fabrication fix]: when the payload skeleton yields
 *  no drawable HealthCardData (metrics/phases elided to null), render a STRUCTURE-PRESERVING empty
 *  card — the payload's OWN title/status/summary chrome kept, metrics/phases coerced to [];
 *  HealthSummaryPanel .map()s the empty arrays to an empty (honest-blank) strip, never a crash.
 *  This REPLACES the old createInitialVoltageCurrentSnapshot(0) fallback, which returned a
 *  `source:'mock'` view-model with FABRICATED phase readings + a "Motor start sag" event.
 *  Never fabricates. */
function honestEmptyHealth(seed: any): HealthCardData {
  const s = seed && typeof seed === "object" ? seed : {};
  return {
    title: typeof s.title === "string" ? s.title : "Voltage Health",
    status: (s.status && typeof s.status === "object")
      ? { ...s.status, label: s.status.label ?? "—" }
      : { label: "—", tone: "neutral" as any },
    statusVocab: s.statusVocab,
    insightKey: s.insightKey,
    insightVocab: s.insightVocab,
    summary: s.summary,
    band: s.band,
    metrics: [],
    phases: [],
    insight: typeof s.insight === "string" ? s.insight : "",
  };
}

function drawable(data: any): data is HealthCardData {
  return !!data && Array.isArray(data.metrics) && Array.isArray(data.phases);
}

function HealthCard({ health }: { health: any }) {
  // 1) payload skeleton (Layer-2 completed — real or honest-blank; data leaves may be elided).
  let data: HealthCardData | undefined = health?.data;

  // 2) DRAW GUARANTEE — if the skeleton isn't drawable, HONEST-EMPTY (structure kept, NO mock seed).
  if (!drawable(data)) data = honestEmptyHealth(health?.data);

  return (
    <div className="h-full">
      <HealthSummaryPanel data={data} phaseVariant={health?.phaseVariant ?? "rows"} />
    </div>
  );
}

export const card43 = (p: any): React.ReactNode =>
  <HealthCard health={p?.health} />;
