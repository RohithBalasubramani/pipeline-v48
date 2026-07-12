// guards/walk.ts — THE execution order (split F12, 2026-07-12). The monolith encoded cross-rule order in
// prose; this array IS the order now — byte-identical to the monolith walk. Constraints:
//   • markDataRows runs FIRST at every dict (parents are visited before children — residual-dash reads the
//     POINT_ROWS/PANEL_ROWS marks the parent visit made).
//   • fixReferenceLines (g15) runs BEFORE fixBadge (g2 — a watch-line is not a badge; info must never be
//     stamped on it) and BEFORE rehydrateSiblingObjects/dashResidualNulls (g4/g9 — a deleted slot cannot be
//     rehydrated or dashed into NaN geometry).
//   • dashResidualNulls runs LAST (after every shape/contract rule has had its say on the dict).
import { isDict } from "./_shared";
import { markDataRows, dashResidualNulls } from "./residual-dash";
import { fixFreshness } from "./freshness";
import { fixReferenceLines } from "./ref-lines";
import { fixBadge } from "./tones";
import { fixResolvedFilter } from "./event-filter";
import { fixNoAssertFallback } from "./no-assert";
import { fixSankey } from "./sankey";
import { fixHeatmapSection } from "./heatmap";
import { fixStripControls } from "./strip-controls";
import { fixEnergyDistributionVm } from "./energy-distribution";
import { fixCompositeSampling } from "./composite-sampling";
import { fixEventRecords } from "./event-records";
import { rehydrateSiblingObjects } from "./rehydrate";
import { fixDigitChrome } from "./digits";

export function walk(node: any): void {
  if (Array.isArray(node)) {
    for (const el of node) if (el != null && typeof el === "object") walk(el);
    return;
  }
  if (!isDict(node)) return;
  markDataRows(node);
  fixFreshness(node);
  fixReferenceLines(node);
  fixBadge(node);
  fixResolvedFilter(node);
  fixNoAssertFallback(node);
  fixSankey(node);
  fixHeatmapSection(node);
  fixStripControls(node);
  fixEnergyDistributionVm(node);
  fixCompositeSampling(node);
  fixEventRecords(node);
  rehydrateSiblingObjects(node);
  fixDigitChrome(node);
  dashResidualNulls(node);
  for (const v of Object.values(node)) if (v != null && typeof v === "object") walk(v);
}
