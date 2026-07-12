// guards/composite-sampling.ts — g13 CompositeChartCard sampling default (split F12, 2026-07-12).

// ── g13: CompositeChartCard vm ({leftAxis,rightAxis,…}) — the SamplingPicker prop is required
// (`value.preset` read in a useState initializer). {preset:'today', range:null} = the picker's neutral UI-control
// selection (a control default, not a data claim).
export function fixCompositeSampling(d: Record<string, any>): void {
  if ("leftAxis" in d && "rightAxis" in d && Array.isArray(d.series) && d.sampling == null) {
    d.sampling = { preset: "today", range: null };
  }
}
