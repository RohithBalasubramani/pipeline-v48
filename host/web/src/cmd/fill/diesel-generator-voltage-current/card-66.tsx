import React from "react";
// Card 66 — Voltage Live Health (page diesel-generator-asset-dashboard/voltage-current, CMD V2 DG "Voltage & Current"
// tab). HealthSummaryPanel fed its OWN Layer-2 payload's voltage `data` (HealthCardData), phaseVariant="bars" (11 kV L-L
// genset labels).
//
// host-served is RETIRED → the payload IS the render source. The harvested story args are `{ variant, data:
// HealthCardData }` (real neuract values + honest-blank '—'), so we read `payload.data` straight. Honest-degrade: a
// payload with no usable HealthCardData (Layer 2 elided the metrics/phases leaves) falls back to CMD V2's OWN
// structured-empty slice — NEVER a blank/null card, NEVER a mock/seed number. NO date/range control → no onDateChange.
import { HealthSummaryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { unavailableHealth } from "./empty-view-model";
import { healthData, healthPhaseVariant, sanitizeHealth } from "./payload-unwrap";

function VoltageHealthCard({ payload }: { payload: any }) {
  const fromPayload = healthData(payload);
  // ALWAYS-DRAW: prefer the payload's HealthCardData; if it's unusable (Layer 2 elided the metrics/phases arrays), fall
  // back to CMD V2's OWN structured-empty slice (metrics/phases '—') so the panel draws its chrome instead of a
  // blank/null card. NEVER return null.
  const usable = (d: any) => !!d && Array.isArray(d.metrics) && Array.isArray(d.phases);
  const data = usable(fromPayload) ? fromPayload! : unavailableHealth("voltage");
  // sanitizeHealth: per-leaf guard-rail (drop a labels-less band, finitize bar pcts) — see payload-unwrap.
  return <HealthSummaryPanel data={sanitizeHealth(data)} phaseVariant={healthPhaseVariant(payload)} />;
}

export const card66 = (p: any): React.ReactNode => <VoltageHealthCard payload={p} />;
