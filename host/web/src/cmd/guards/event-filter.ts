// guards/event-filter.ts — g5 resolvedFilter derivation via CMD_V2 own rule (split F12, 2026-07-12).
import { resolveEventFilter } from "@cmd-v2/components/charts/primitives/eventFilterRules";
import { isDict, blank } from "./_shared";

// ── g5: a null/absent 'resolvedFilter' beside a 'filterSelection' → derived by CMD_V2's OWN exported
// resolveEventFilter (the exact rule the producer uses). Underivable selection → left alone.
export function fixResolvedFilter(d: Record<string, any>): void {
  const sel = d.filterSelection;
  if (!isDict(sel) || blank(sel.preset) || d.resolvedFilter != null) return;
  try {
    d.resolvedFilter = resolveEventFilter({
      preset: sel.preset,
      resample: blank(sel.resample) ? "hourly" : sel.resample,
      customDate: sel.customDate ?? "",
      rangeStart: sel.rangeStart ?? "",
      rangeEnd: sel.rangeEnd ?? "",
    } as any);
  } catch {
    /* underivable → leave (Boundary net) */
  }
}
