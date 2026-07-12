// guards/energy-distribution.ts — g12 energy-distribution vm chrome completion (split F12, 2026-07-12).
import { isDict } from "./_shared";

// ── g12: energy-distribution vm contract ({sankey,legend,…}) — EnergyInputDistributionCard/EnergyFlowDiagramCard
// deref these chrome subtrees unconditionally. Typed EMPTY completion only (blank headers, empty rosters): structure
// is chrome; no word or number is invented. Never clobbers an existing key.
export function fixEnergyDistributionVm(d: Record<string, any>): void {
  if (!isDict(d.sankey) || !Array.isArray(d.legend)) return;
  const ensure = (k: string, v: any) => {
    if (d[k] == null) d[k] = v;
  };
  ensure("inputCardTitle", "");
  ensure("allRowLabel", "");
  ensure("flowCardTitle", "");
  ensure("stageUnit", "");
  ensure("aiSummary", "");
  ensure("sourcesSection", { groupLabel: "", columnHeader: "" });
  ensure("consumersSection", { groupLabel: "", columnHeader: "" });
  ensure("supplied", { label: "", unit: "" });
  ensure("consumed", { label: "", unit: "" });
  ensure("sources", []);
  ensure("consumers", []);
}
