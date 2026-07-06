import React from "react";
// Card 68 — Current Live Health (page diesel-generator-asset-dashboard/voltage-current, CMD V2 DG "Voltage & Current"
// tab). HealthSummaryPanel fed its OWN Layer-2 payload's current `data` (HealthCardData), phaseVariant="bars" (R/Y/B/N
// genset line currents).
//
// ems_backend is RETIRED → the payload IS the render source. The harvested story args are `{ variant, data:
// HealthCardData }` (real neuract values + honest-blank '—'), so we read `payload.data` straight. Honest-degrade: a
// payload with no usable HealthCardData falls back to CMD V2's OWN structured-empty slice — NEVER a blank/null card,
// NEVER a mock/seed number. NO date/range control → no onDateChange.
import { HealthSummaryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { unavailableHealth } from "./empty-view-model";
import { healthData, healthPhaseVariant, sanitizeHealth } from "./payload-unwrap";

function CurrentHealthCard({ payload }: { payload: any }) {
  const fromPayload = healthData(payload);
  // ALWAYS-DRAW: prefer the payload's HealthCardData; if unusable, fall back to CMD V2's OWN structured-empty slice
  // (metrics/phases '—') so the panel draws its chrome instead of a blank/null card. NEVER return null.
  const usable = (d: any) => !!d && Array.isArray(d.metrics) && Array.isArray(d.phases);
  const data = usable(fromPayload) ? fromPayload! : unavailableHealth("current");
  // sanitizeHealth: per-leaf guard-rail (drop a labels-less band, finitize bar pcts) — see payload-unwrap.
  return <HealthSummaryPanel data={sanitizeHealth(data)} phaseVariant={healthPhaseVariant(payload)} />;
}

export const card68 = (p: any): React.ReactNode => <CurrentHealthCard payload={p} />;
