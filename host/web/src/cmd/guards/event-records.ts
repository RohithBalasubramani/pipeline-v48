// guards/event-records.ts — g14 blank-severity event-record omission (split F12, 2026-07-12).
import { isDict, blank } from "./_shared";

// ── g14: event-record contract — an 'events' array entry with a blank 'severity' is an UNDERIVABLE event (the
// executor found no sample: idx '—', blank title/why). CMD_V2 rails deref SEV[severity] (warn/danger only) per record,
// so the honest, non-fabricating handling is OMISSION of that record — an empty rail is the component's own state for
// "no derivable events". Key-shape driven (an array under an *events key whose dict entries carry 'severity').
export function fixEventRecords(d: Record<string, any>): void {
  for (const [k, v] of Object.entries(d)) {
    if (!/events$/i.test(k) || !Array.isArray(v)) continue;
    if (!v.some((e: any) => isDict(e) && "severity" in e)) continue;
    d[k] = v.filter((e: any) => !(isDict(e) && "severity" in e && blank(e.severity)));
  }
}
