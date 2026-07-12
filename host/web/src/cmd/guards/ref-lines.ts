// guards/ref-lines.ts — g15 reference-line contract (split F12, 2026-07-12). ORDER (enforced by walk.ts):
// runs BEFORE tones (a watch-line is not a badge) and BEFORE rehydrate/residual-dash (a deleted slot cannot be
// rehydrated or dashed into NaN geometry).
import { isDict, finite } from "./_shared";

// ── g15: reference-line contract (see header). Every payload family below feeds CMD_V2's ReferenceLine primitive
// (TONE_PRESETS[tone].pillBg) at yScale(entry.value). Contract population, verified across all served responses:
//   watchLines[]     {tone,color,label,value}                (LoadImpactChart      — payload tone + payload value)
//   thresholds[]     {color,label,labelColor,value}          (PhaseMonitorChart / ScoreHistoryCard — payload value)
//   referenceLines[] {id,name,unit,separator,tone,placement} (energy-power Charts  — payload tone; value from points,
//                                                             component-gated `!(value > 0)`)
//   maxLine/minLine  {label,value}                           (DistortionProfileChart — payload value, conditional
//                                                             `slice.maxLine && …` render)
//   floor            {label,value}                           (CompositeChartCard  — conditional `view.floor ?` render)
// Non-{label,value} lookalikes (sparkline/timeline/bandThresholds/backendHeadline) fail the shape gate untouched.
const REF_LINE_TONES = new Set(["reference", "threshold", "advisory", "watch"]); // ReferenceLine.tsx TONE_PRESETS keys
const REF_LINE_ARRAY_KEY = /(lines|thresholds)$/i;
const REF_LINE_SLOT_KEY = /(max|min|avg|target|watch|ref|reference|threshold|limit|critical|floor)line$|^floor$/i;
const refLineShaped = (e: any) => isDict(e) && "label" in e && "value" in e;
export function fixReferenceLines(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (Array.isArray(v) && REF_LINE_ARRAY_KEY.test(k)) {
      // hazard 1 — unmeasured Y: a {label,value} entry whose value is non-finite cannot be scaled (SVG y1=NaN);
      // the unmeasured reference is drawn NOWHERE (entry omitted). Entries without a 'value' slot resolve their Y
      // from the chart's own points behind the component's own finite gate — left alone.
      const kept = v.filter((e: any) => !(refLineShaped(e) && !finite(e.value)));
      if (kept.length !== v.length) d[k] = kept;
      // hazard 2 — tone outside the ReferenceLine enum ('' / '—' / a badge word): TONE_PRESETS[tone].pillBg throws.
      // DELETE the key so the component's OWN neutral fires (`line.tone ?? 'watch'` / default-param 'reference') —
      // the map-derived neutral via the component's own documented fallback; never an asserted severity.
      for (const e of d[k]) {
        if (isDict(e) && "tone" in e && !(typeof e.tone === "string" && REF_LINE_TONES.has(e.tone))) delete e.tone;
      }
    } else if (REF_LINE_SLOT_KEY.test(k)) {
      // dict SLOT ({label,value} under maxLine/minLine/floor…): non-finite value OR a null slot → DELETE the key so
      // the component's own `slice.maxLine && …` conditional skips the primitive (g4 can then never rehydrate it
      // into chrome and g9 can never dash it into NaN geometry — order: g15 runs before both).
      if ((refLineShaped(v) && !finite(v.value)) || v === null) delete d[k];
    }
  }
}
