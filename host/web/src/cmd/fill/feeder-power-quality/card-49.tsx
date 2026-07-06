import React from "react";
// Card 49 — LoadImpactChart, a rail chart WITH a CMD V2 <SamplingPicker>. FRAMES ARE RETIRED: the ONLY data source is
// the Layer-2 completed payload (`{ variant, loadImpact: PowerQualityData['loadImpact'] }` — real neuract series +
// honest-blank). We render LoadImpactChart DIRECTLY from `payload.loadImpact`, injecting the tab's real sampling chrome.
// Same per-card date wiring as card 48: <SamplingPicker> commits a SamplingSelection → date_window → onDateChange.
import { LoadImpactChart } from "@cmd-v2/components/charts/primitives";
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";
import { POWER_QUALITY_SAMPLING_PRESETS } from "@cmd-v2/pages/electrical/tabs/power-quality/powerQualitySampling";
import { createPowerQualityViewModel } from "@cmd-v2/pages/electrical/tabs/power-quality/viewModel";
import type {
  PowerQualityData,
  PowerQualitySnapshot,
} from "@cmd-v2/pages/electrical/tabs/power-quality/types";
import { samplingToDateWindow } from "./date-window";
import { SAMPLING, SAMPLING_RESOLUTION_OPTIONS } from "./sampling";

/** True when a load-impact slice is drawable: the selected view has plottable series + watchLines AND — since the rail
 *  <SegmentedControl> lets the user toggle to ANY view — EVERY view is structurally array-safe (each slice's `series`,
 *  `watchLines`, `yTicks` and `xLabels` are arrays; the SVG `.map`s / `Math.max`es all of them). A swapped-in / partial
 *  / honest-blanked payload that fails either check falls back to the fully-structured empty slice (drawable for all
 *  views), never a crash on toggle. */
function hasUsableLoadImpact(data: any): boolean {
  if (!data || !data.views || typeof data.views !== "object") return false;
  const views: any = data.views;
  const allViewsSafe = Object.keys(views).every(
    (k) =>
      views[k] &&
      Array.isArray(views[k].series) &&
      Array.isArray(views[k].watchLines) &&
      Array.isArray(views[k].yTicks) &&
      Array.isArray(views[k].xLabels),
  );
  if (!allViewsSafe) return false;
  const slice: any = views[data.view];
  return (
    !!slice &&
    Array.isArray(slice.series) &&
    slice.series.length > 0 &&
    Array.isArray(slice.watchLines)
  );
}

/** CMD V2's OWN structured EMPTY load impact (valid views/axes/toggle, empty series + watchLines) — drawn when the
 *  payload slice isn't usable so the chart shows its chrome instead of a blank/null card. A null-limit base snapshot
 *  lets the slice builders fall back to IEEE 519 default limits (no frame, no seed). */
function emptyLoadImpact(): PowerQualityData["loadImpact"] {
  const base = { iThd: {}, vThd: {}, h5: {}, h7: {} } as unknown as PowerQualitySnapshot;
  return createPowerQualityViewModel(base).loadImpact;
}

/** Card 49 — LoadImpactChart. payload = { loadImpact } (story args). Render the payload slice when usable, else a
 *  structured-empty slice — ALWAYS draws. Same per-card date wiring as card 48. */
function LoadImpactFill({
  payload,
  onDateChange,
}: {
  payload: any;
  onDateChange?: (dw: any) => void;
}) {
  const slice = payload?.loadImpact;
  const drawable: PowerQualityData["loadImpact"] = hasUsableLoadImpact(slice)
    ? (slice as PowerQualityData["loadImpact"])
    : emptyLoadImpact();

  return (
    <LoadImpactChart
      data={drawable}
      className="h-full w-full"
      sampling={SAMPLING}
      onSamplingChange={(next: SamplingSelection) => onDateChange?.(samplingToDateWindow(next))}
      samplingPresets={POWER_QUALITY_SAMPLING_PRESETS}
      samplingResolutionOptions={SAMPLING_RESOLUTION_OPTIONS}
      samplingShowCalendar={false}
    />
  );
}

export const card49 = (p: any, _f?: any, onDateChange?: (dw: any) => void) => (
  <LoadImpactFill payload={p} onDateChange={onDateChange} />
);
