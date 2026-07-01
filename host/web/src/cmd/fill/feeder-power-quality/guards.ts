// Frame-shape guards for the individual-feeder-meter-shell/power-quality page.
// The host hands each card frames[card.endpoint] (else the page frame), so a card may receive EITHER envelope
// (power-quality-summary → widgets, or power-quality-history → buckets); we discriminate on the frame shape and
// feed the matching mapper, falling back to the payload.

// True when the frame looks like the per-feeder summary aggregate envelope (carries `widgets`, not `buckets`).
export const isAggregateFrame = (f: any): boolean =>
  !!f && typeof f === "object" && f.widgets != null && !Array.isArray(f.widgets) && !Array.isArray(f.buckets);

// True when the frame looks like the power-quality-history envelope (carries `buckets`).
export const isHistoryFrame = (f: any): boolean =>
  !!f && typeof f === "object" && Array.isArray(f.buckets);
