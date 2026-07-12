// guards/tones.ts — g2 badge/tone contract + KNOWN_TONES (split F12, 2026-07-12).
import { blank } from "./_shared";

// ── g2 vocab: the UNION of every state-keyed style map a served tone can index in the reachable CMD_V2 tree —
// mirrored per-map from the READ-ONLY sources (a payload tone carrying one of these keys is a REAL state and is
// never touched; anything else derefs undefined in at least one map and throws):
//   • StatusPill.STATUS_PILL_TONES / KpiStatStrip.KPI_STATUS_DOT_PRESETS → normal|alarm|watch|info
//   • StatusBadge.PALETTE / AiInsightCard.AI_INSIGHT_TONE               → fail|critical|warning|success|info|neutral
//   • ups shared/adapters.STATUS_PILL_TONE (domain)                      → success|warning|danger
//   • HealthSummaryPanel.DELTA_TONE                                      → good|bad|neutral
//   • KpiMiniCard.TREND_PRESETS                                          → stable|rising|falling
//   • UpsCapacityCard deltaTone union (string-compare, no map)           → positive|negative|neutral
//   • misc literal unions (string-compare consumers)                     → default
//   • ReferenceLine.TONE_PRESETS (the g15 family — normalized THERE by key deletion, never stamped 'info' here;
//     listed so a REAL ref-line tone passing this rule is never clobbered) → reference|threshold|advisory|watch
export const KNOWN_TONES = new Set([
  "normal", "alarm", "watch", "info",
  "fail", "critical", "warning", "success", "neutral",
  "danger",
  "good", "bad",
  "stable", "rising", "falling",
  "positive", "negative", "default",
  "reference", "threshold", "advisory",
]);
export const DS_TONES = new Set(["normal", "alarm", "watch", "info"]); // StatusPill/KPI-dot enum — the 'dsTone' seam
export const badTone = (t: any) => blank(t) || typeof t !== "string" || !KNOWN_TONES.has(t);

// ── g2: badge/tone dicts + domain Δ-chips (see header). Never overrides a tone that is a real key of ANY reachable
// style map (KNOWN_TONES). A blank OR unknown tone ('' / '—' / garbage — all seen in served payloads) becomes 'info'
// — the ONE token valid through BOTH vocabularies: a DS enum natively AND the UPS DOMAIN map via the shims.ts alias
// — teal informational chrome, the least assertive tone; the label stays blank so no state word is asserted.
// NEVER a domain word ('success'): the SAME HealthMetric-row shape feeds the DS map DIRECTLY in ThermalLifeCard
// (KPI_STATUS_DOT_PRESETS['success'].dot throws — card 74).
export function fixBadge(d: Record<string, any>): void {
  if ("tone" in d && "label" in d && badTone(d.tone)) d.tone = "info";
  // RailStatusPill reads `dsTone` FIRST; a blank STRING defeats its `?? RAIL_TONE_TO_DS[tone]` fallback, and a
  // non-DS word ('success'/'—') indexes STATUS_PILL_TONES[dsTone] undefined → .bg throws. DS enum only.
  if ("dsTone" in d && (blank(d.dsTone) || typeof d.dsTone !== "string" || !DS_TONES.has(d.dsTone))) {
    const map: Record<string, string> = { success: "normal", warning: "alarm" };
    d.dsTone = (typeof d.tone === "string" && map[d.tone]) || "info";
  }
  if ("deltaTone" in d && badTone(d.deltaTone)) d.deltaTone = "info";
}
