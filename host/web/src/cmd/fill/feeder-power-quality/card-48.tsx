import React from "react";
// Card 48 — DistortionProfileChart, a rail chart WITH a CMD V2 <SamplingPicker>; thread onDateChange so its own date
// control re-fetches this card's frame.
import { DistortionProfileChart } from "@cmd-v2/components/charts/primitives";
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";
import { POWER_QUALITY_SAMPLING_PRESETS } from "@cmd-v2/pages/electrical/tabs/power-quality/powerQualitySampling";
import type {
  PowerQualityData,
  PowerQualitySnapshot,
} from "@cmd-v2/pages/electrical/tabs/power-quality/types";
import { liveSnapshot, liveViewModel } from "./mappers";
import { samplingToDateWindow } from "./date-window";
import { SAMPLING, SAMPLING_RESOLUTION_OPTIONS } from "./sampling";

/** Card 48 — DistortionProfileChart. payload = { distortionProfile } (story args). Live: build the view-model from a
 *  history frame and use its distortionProfile slice; else the payload default. The chart's <SamplingPicker> commits a
 *  SamplingSelection via onSamplingChange → translated to a date_window and handed to onDateChange so the host re-fetches
 *  THIS card's history frame for the new window. */
function DistortionProfileFill({
  payload,
  frame,
  onDateChange,
}: {
  payload: any;
  frame?: any;
  onDateChange?: (dw: any) => void;
}) {
  let data: PowerQualityData["distortionProfile"] = payload?.distortionProfile;
  try {
    // The slice builders read per-row THD limits off the snapshot; use the page's summary frame when it rode in on the
    // same envelope, otherwise a null-limit base snapshot (limits fall back to defaults inside the builders).
    const base = liveSnapshot(frame) ?? ({ iThd: {}, vThd: {}, h5: {}, h7: {} } as unknown as PowerQualitySnapshot);
    const vm = liveViewModel(frame, base);
    if (vm) data = vm.distortionProfile;
  } catch {
    /* keep payload default */
  }
  // guard: DistortionProfileChart indexes data.views[data.view] then maps that slice's .series
  // (data.views[view].series.map, and slice.series[0].values). Layer 2 elides those leaf arrays,
  // so render only when the selected view's series is a non-empty array — else clean placeholder.
  if (!data || !data.views || typeof data.views !== "object") return null;
  {
    const slice: any = (data.views as any)[data.view];
    if (!slice || !Array.isArray(slice.series) || slice.series.length === 0) return null;
  }
  return (
    <DistortionProfileChart
      data={data}
      sampling={SAMPLING}
      onSamplingChange={(next: SamplingSelection) => onDateChange?.(samplingToDateWindow(next))}
      samplingPresets={POWER_QUALITY_SAMPLING_PRESETS}
      samplingResolutionOptions={SAMPLING_RESOLUTION_OPTIONS}
      samplingShowCalendar={false}
    />
  );
}

export const card48 = (p: any, f?: any, onDateChange?: (dw: any) => void) => (
  <DistortionProfileFill payload={p} frame={f} onDateChange={onDateChange} />
);
