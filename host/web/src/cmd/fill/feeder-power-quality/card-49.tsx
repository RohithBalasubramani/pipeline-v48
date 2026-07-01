import React from "react";
// Card 49 — LoadImpactChart, a rail chart WITH a CMD V2 <SamplingPicker>; thread onDateChange so its own date control
// re-fetches this card's frame. Same per-card date wiring as card 48.
import { LoadImpactChart } from "@cmd-v2/components/charts/primitives";
import type { SamplingSelection } from "@cmd-v2/components/charts/primitives";
import { POWER_QUALITY_SAMPLING_PRESETS } from "@cmd-v2/pages/electrical/tabs/power-quality/powerQualitySampling";
import type {
  PowerQualityData,
  PowerQualitySnapshot,
} from "@cmd-v2/pages/electrical/tabs/power-quality/types";
import { liveSnapshot, liveViewModel } from "./mappers";
import { samplingToDateWindow } from "./date-window";
import { SAMPLING, SAMPLING_RESOLUTION_OPTIONS } from "./sampling";

/** Card 49 — LoadImpactChart. payload = { loadImpact } (story args). Live: build the view-model from a history frame
 *  and use its loadImpact slice; else the payload default. Same per-card date wiring as card 48: the chart's
 *  <SamplingPicker> commits a SamplingSelection → date_window → onDateChange (host re-fetches this card's frame). */
function LoadImpactFill({
  payload,
  frame,
  onDateChange,
}: {
  payload: any;
  frame?: any;
  onDateChange?: (dw: any) => void;
}) {
  let data: PowerQualityData["loadImpact"] = payload?.loadImpact;
  try {
    const base = liveSnapshot(frame) ?? ({ iThd: {}, vThd: {}, h5: {}, h7: {} } as unknown as PowerQualitySnapshot);
    const vm = liveViewModel(frame, base);
    if (vm) data = vm.loadImpact;
  } catch {
    /* keep payload default */
  }
  // guard: LoadImpactChart indexes data.views[data.view] then maps that slice's .series AND .watchLines
  // (slice.series.map, slice.watchLines.map, slice.series[0].values). Layer 2 elides those leaf arrays,
  // so render only when the selected view's series + watchLines are arrays — else clean placeholder.
  if (!data || !data.views || typeof data.views !== "object") return null;
  {
    const slice: any = (data.views as any)[data.view];
    if (
      !slice ||
      !Array.isArray(slice.series) ||
      slice.series.length === 0 ||
      !Array.isArray(slice.watchLines)
    )
      return null;
  }
  return (
    <LoadImpactChart
      data={data}
      sampling={SAMPLING}
      onSamplingChange={(next: SamplingSelection) => onDateChange?.(samplingToDateWindow(next))}
      samplingPresets={POWER_QUALITY_SAMPLING_PRESETS}
      samplingResolutionOptions={SAMPLING_RESOLUTION_OPTIONS}
      samplingShowCalendar={false}
    />
  );
}

export const card49 = (p: any, f?: any, onDateChange?: (dw: any) => void) => (
  <LoadImpactFill payload={p} frame={f} onDateChange={onDateChange} />
);
