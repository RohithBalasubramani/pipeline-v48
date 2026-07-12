// guards/strip-controls.ts — g11 events/PQ top-strip controls shape (split F12, 2026-07-12).
import { isDict } from "./_shared";

// ── g11: events/PQ top-strip presentation ({tiles,tileOrder}) — PqTopStrip reads pres.controls.* unconditionally;
// the empty controls shape satisfies every read (all inner options are optional → EventStripControls' own defaults).
export function fixStripControls(d: Record<string, any>): void {
  if (Array.isArray(d.tiles) && Array.isArray(d.tileOrder) && !isDict(d.controls)) {
    d.controls = { ariaLabels: {} };
  }
}
