import React from "react";
// Card 21 · Current Distribution (radar) — lt-pcc panel-overview Voltage&Current tab.
//
// PAYLOAD-DIRECT (host-served RETIRED — `frame` is always empty now). Priority:
// payload → CMD V2 HONEST-EMPTY view-model. CurrentDistributionCard does
// `period.panels.filter(...).map(...)`; if the payload elided the panels leaf, fall back to
// the page's OWN honest-empty model (empty panels, chrome only, NO fabrication). NEVER null.
// The old live-aggregate-frame branch is dead code and was DELETED.

import { CurrentDistributionCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/Cards";
import type { PeriodBucket } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/voltage-current/types";
import { SectionRadar } from "../../section-split";

import {
  bundleFrom,
  fallbackViewModel,
  defaultPresentation,
  hasPanels,
} from "./view-model";

function DistributionCard({ distribution }: { distribution: any }) {
  // SECTION COMPARE [sections overlay]: the executor stamped `sectionCompare` — render the payload-driven comparison
  // radar (CMD_V2 ComparisonRadarChart primitive, one polygon per bus section, AI-morphable labels/colors via
  // pres.sections). Without the stamp the original card renders byte-identically below.
  if (Array.isArray(distribution?.sectionCompare) && distribution.sectionCompare.length >= 2
      && Array.isArray(distribution?.period?.panels) && distribution.period.panels.length > 0) {
    return (
      <div className="h-full">
        <SectionRadar distribution={distribution} />
      </div>
    );
  }
  // 1) payload (Layer-2 completed — real or honest-blank).
  let period: PeriodBucket = distribution?.period;
  let selectedPanelId: string = distribution?.selectedPanelId;

  // 2) DRAW GUARANTEE — backfill panel-bearing period + selected id from the honest-empty model.
  if (!hasPanels(period)) {
    const b = bundleFrom(fallbackViewModel());
    period = b.period;
    selectedPanelId = selectedPanelId || b.selectedPanelId;
  }
  if (!selectedPanelId) selectedPanelId = period.panels[0]?.id ?? "";

  const pres = distribution?.pres ?? defaultPresentation().currentDistribution;
  return (
    <div className="h-full">
      <CurrentDistributionCard pres={pres} period={period} selectedPanelId={selectedPanelId} />
    </div>
  );
}

export const card21 = (p: any): React.ReactNode =>
  <DistributionCard distribution={p?.distribution} />;
