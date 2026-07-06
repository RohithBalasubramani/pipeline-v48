import React from "react";
// Card 48 — DistortionProfileChart, a rail chart WITH a CMD V2 <SamplingPicker>. FRAMES ARE RETIRED: the ONLY data
// source is the Layer-2 completed payload (`{ variant, distortionProfile: PowerQualityData['distortionProfile'] }` —
// real neuract series + honest-blank). We render DistortionProfileChart DIRECTLY from `payload.distortionProfile`,
// injecting the tab's real sampling chrome. thread onDateChange so the date control re-fetches this card's window.
import { DistortionProfileChart } from "@cmd-v2/components/charts/primitives";
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";
import { POWER_QUALITY_SAMPLING_PRESETS } from "@cmd-v2/pages/electrical/tabs/power-quality/powerQualitySampling";
import { createPowerQualityViewModel } from "@cmd-v2/pages/electrical/tabs/power-quality/viewModel";
import type {
  PowerQualityData,
  PowerQualitySnapshot,
} from "@cmd-v2/pages/electrical/tabs/power-quality/types";
import { samplingToDateWindow } from "./date-window";
import { SAMPLING, SAMPLING_RESOLUTION_OPTIONS } from "./sampling";

/** True when a distortion slice is drawable: the selected view has plottable series AND — since the rail
 *  <SegmentedControl> lets the user toggle to ANY view — EVERY view is structurally array-safe (each slice's `series`
 *  is an array). A swapped-in / partial / honest-blanked payload that fails either check falls back to the fully-
 *  structured empty slice (which the chart draws for all views), never a crash on toggle. */
function hasUsableDistortion(data: any): boolean {
  if (!data || !data.views || typeof data.views !== "object") return false;
  const views: any = data.views;
  const allViewsSafe = Object.keys(views).every((k) => views[k] && Array.isArray(views[k].series));
  if (!allViewsSafe) return false;
  const slice: any = views[data.view];
  return !!slice && Array.isArray(slice.series) && slice.series.length > 0;
}

/** CMD V2's OWN structured EMPTY distortion profile (valid views/axes/toggle, empty series) — drawn when the payload
 *  slice isn't usable so the chart shows its chrome instead of a blank/null card. A null-limit base snapshot lets the
 *  slice builders fall back to IEEE 519 default limits (no frame, no seed). */
function emptyDistortion(): PowerQualityData["distortionProfile"] {
  const base = { iThd: {}, vThd: {}, h5: {}, h7: {} } as unknown as PowerQualitySnapshot;
  return createPowerQualityViewModel(base).distortionProfile;
}

/** Card 48 — DistortionProfileChart. payload = { distortionProfile } (story args). Render the payload slice when usable,
 *  else a structured-empty slice — ALWAYS draws. The chart's <SamplingPicker> commits a SamplingSelection →
 *  date_window → onDateChange (host re-fetches THIS card's frame for the new window). */
function DistortionProfileFill({
  payload,
  onDateChange,
}: {
  payload: any;
  onDateChange?: (dw: any) => void;
}) {
  const slice = payload?.distortionProfile;
  const drawable: PowerQualityData["distortionProfile"] = hasUsableDistortion(slice)
    ? (slice as PowerQualityData["distortionProfile"])
    : emptyDistortion();

  return (
    <DistortionProfileChart
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

export const card48 = (p: any, _f?: any, onDateChange?: (dw: any) => void) => (
  <DistortionProfileFill payload={p} onDateChange={onDateChange} />
);
