import React from "react";
// Card 45 — Current Health Summary (page individual-feeder-meter-shell/voltage-current, CMD V2 Equipment-Detail
// "Voltage & Current" tab). FRAMES ARE RETIRED: the ONLY data source is the Layer-2 completed payload (real neuract
// values + honest-blank '—', shape = the Storybook story args `{ variant, health: { data, phaseVariant } }`). We render
// HealthSummaryPanel DIRECTLY from `payload.health.data` + `payload.health.phaseVariant`, guarded by sanitizeHealth.
// Card 45 renders a health snapshot with NO date/range/sampling control — so it carries no onDateChange.
import { HealthSummaryPanel } from "@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel";
import { healthData, healthPhaseVariant, sanitizeHealth, unavailableHealth } from "./payload-unwrap";

/** Card 45 — Current Health Summary: HealthSummaryPanel fed the payload's `health.data`. */
function CurrentHealthCard({ payload }: { payload: any }) {
  const slice = healthData(payload);
  // ALWAYS-DRAW: use the payload slice when it carries metrics+phases; else CMD V2's OWN structured-empty slice
  // (metrics/phases "—") so the panel draws chrome instead of a blank/null card. sanitizeHealth then guards whichever
  // won: a phase's widthPct/markerPct honest-dashed to '—' (sits beside a `unit`, so display_dash → '—') can NEVER
  // reach PhaseBarRows clampPct/CSS-% and render `width: NaN%`; band.markerPct falls back to a finite centre. The '—'
  // text VALUES pass through untouched. Matches the sanitizeSupply pattern. [NaN-guard]
  const usable = (d: any) => !!d && Array.isArray(d.metrics) && Array.isArray(d.phases);
  const data = sanitizeHealth(usable(slice) ? slice! : unavailableHealth("current"));
  return <HealthSummaryPanel data={data} phaseVariant={healthPhaseVariant(payload)} />;
}

export const card45 = (p: any): React.ReactNode => <CurrentHealthCard payload={p} />;
