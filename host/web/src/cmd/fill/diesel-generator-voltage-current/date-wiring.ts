// date control wiring (HistoryPanel SamplingPicker → host window) for the diesel-generator-voltage-current fill cards.
// ONE shared implementation lives in ../shared/sampling-window — re-exported so this folder's importers keep their path.
export { defaultSampling, samplingToWindow, withDateControl } from "../shared/sampling-window";
