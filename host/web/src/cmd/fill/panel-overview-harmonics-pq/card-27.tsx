/**
 * card 27 — SignatureCard (harmonic-signature radar).
 *
 * PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). The Layer-2
 * completed payload IS the render source: payload.signature = { pres, period, selectedPanelId,
 * apiSignature }, carrying REAL per-feeder harmonic spokes or honest-blank. The old live
 * snapshotFromFrame(frame) branch AND the buildPQPeriods() fabrication fallback (synthetic
 * harmonic waves — a seed leak) are DELETED. SignatureCard does `period.panels.find(...)`, so
 * an empty period (`panels: []`) renders an honest-empty radar (chrome + no spokes), NEVER a mock.
 */
import React from "react";

import { SignatureCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/HarmonicsPqTab";
import { buildHpqPresentation } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/viewModel";
import type { PQPeriod } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/harmonics-pq/types";

import { emptyPeriod, emptyPeriodWithRow } from "./derive";

export function renderSignature(payload: any): React.ReactNode {
  const args = payload?.signature ?? payload ?? {};
  let pres = args.pres ?? buildHpqPresentation().signature;
  const apiSignature = args.apiSignature;
  // SignatureCard's MOCK branch (no apiSignature) reads `selected.h3/h5/…` UNGUARDED — an
  // empty period would crash it. So on the honest-empty path we hand it a period with ONE
  // blank ('—'/zero) row (flat-at-zero radar), never a fabricated feeder. The API branch
  // guards `selected`, so a truly-empty period is fine there.
  const rawPeriod: PQPeriod | undefined = args.period;
  const period: PQPeriod =
    rawPeriod && Array.isArray(rawPeriod.panels) && rawPeriod.panels.length > 0
      ? rawPeriod
      : apiSignature
        ? (rawPeriod ?? emptyPeriod())
        : emptyPeriodWithRow();
  const selectedPanelId: string = args.selectedPanelId ?? period.panels[0]?.id ?? "";

  // Elided-seed guard: Layer 2 elides `signature.spokes` (a roster array) from the
  // fallback payload, but SignatureCard feeds `pres.spokes` to ComparisonRadarChart
  // which does `spokes.map(...)` unconditionally. A present-but-partial `pres`
  // (missing `spokes`) would crash — so ALWAYS-DRAW by falling back to CMD V2's OWN
  // default presentation signature (which carries a valid `spokes` roster). NEVER null.
  if (!Array.isArray(pres?.spokes)) {
    const def = buildHpqPresentation().signature;
    pres = { ...def, ...(pres ?? {}), spokes: def.spokes };
  }

  return (
    <div className="h-full min-h-0">
      <SignatureCard
        pres={pres}
        period={period}
        selectedPanelId={selectedPanelId}
        apiSignature={apiSignature}
      />
    </div>
  );
}
