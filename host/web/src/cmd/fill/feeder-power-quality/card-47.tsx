import React from "react";
// Card 47 — PowerQualityCard: a now-snapshot summary card (takes only `snapshot`, no SamplingPicker). FRAMES ARE
// RETIRED: the ONLY data source is the Layer-2 completed payload (`{ variant, snapshot: PowerQualitySnapshot }` — real
// neuract values + honest-blank null). We render PowerQualityCard DIRECTLY from `payload.snapshot`, sanitized against a
// typed placeholder so every leaf is a guarded object/null-shape. No date control to wire → onDateChange ignored.
import { PowerQualityCard } from "@cmd-v2/pages/electrical/tabs/power-quality/PowerQualityCard";
import { buildPowerQualityPresentation } from "@cmd-v2/pages/electrical/tabs/power-quality/viewModel";
import type { PowerQualitySnapshot } from "@cmd-v2/pages/electrical/tabs/power-quality/types";

/** Fully-typed placeholder snapshot so the card ALWAYS draws (structure + typed-empty), never a blank/null card. Used
 *  when the payload carries no usable snapshot. */
function placeholderSnapshot(): PowerQualitySnapshot {
  return {
    source: "api",
    availability: "unavailable",
    message: "Power quality data unavailable for this feeder",
    presentation: buildPowerQualityPresentation(),
    ieeeState: null,
    ieeeBadge: null,
    ieeeConstraint: null,
    trendLabel: null,
    trendPctPerHour: null,
    severityLabel: null,
    severityAction: null,
    iThd: { valuePct: null, limitPct: null, scaleMaxPct: null },
    vThd: { valuePct: null, limitPct: null, scaleMaxPct: null },
    h5: { valuePct: null, limitPct: null, scaleMaxPct: null },
    h7: { valuePct: null, limitPct: null, scaleMaxPct: null },
    flickerPst: { value: null, peakToday: null, limit: null, tone: null, statusBadge: null },
    crestFactor: { value: null, ideal: null, tone: null, statusBadge: null },
    likelySource: null,
    filterState: null,
    capacitorBank: null,
    nextPriority: null,
    nextPriorityTone: null,
  };
}

/** Sanitize the (possibly partial / swapped-in / honest-blanked) payload snapshot against the typed placeholder so EVERY
 *  leaf the card reads is guaranteed its guarded null-shape. A spread of a foreign/partial snapshot could overwrite
 *  `iThd`/`flickerPst`/… with `null`/`undefined`, and `SpectrumRow`/the voltage-quality cells then read `.limitPct`/
 *  `.value` off `null` → crash. We keep the placeholder's object-shape for the four spectrum readings + the two
 *  voltage-quality cells whenever the incoming leaf isn't a usable object, and always guarantee a presentation tree.
 *  (sanitizeSupply pattern.) */
function sanitizeSnapshot(snapshot: any): PowerQualitySnapshot {
  const base = placeholderSnapshot();
  if (!snapshot || typeof snapshot !== "object") return base;
  const obj = (v: any, fallback: any) => (v && typeof v === "object" && !Array.isArray(v) ? { ...fallback, ...v } : fallback);
  return {
    ...base,
    ...snapshot,
    presentation:
      (snapshot.presentation && typeof snapshot.presentation === "object" ? snapshot.presentation : undefined) ??
      buildPowerQualityPresentation(),
    iThd: obj(snapshot.iThd, base.iThd),
    vThd: obj(snapshot.vThd, base.vThd),
    h5: obj(snapshot.h5, base.h5),
    h7: obj(snapshot.h7, base.h7),
    flickerPst: obj(snapshot.flickerPst, base.flickerPst),
    crestFactor: obj(snapshot.crestFactor, base.crestFactor),
  };
}

/** Card 47 — PowerQualityCard. payload = { snapshot } (story args). Render the payload's snapshot; sanitize against the
 *  typed placeholder so every leaf is a guarded object/null-shape (a partial/honest-blanked snapshot can't overwrite a
 *  spectrum/VQ leaf with null → crash). NEVER returns null (a null = a blank card, forbidden). */
function PowerQualityCardFill({ payload }: { payload: any }) {
  const safe: PowerQualitySnapshot = sanitizeSnapshot(payload?.snapshot);
  return <PowerQualityCard snapshot={safe} className="h-full w-full" />;
}

export const card47 = (p: any) => <PowerQualityCardFill payload={p} />;
