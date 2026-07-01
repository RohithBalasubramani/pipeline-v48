// Family A: panel-overview aggregate frame → full view-model + per-card view resolution.
import { mapPanelEnergyPowerAggregateToSnapshot } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/mapper";
import { createPanelEnergyPowerViewModel } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/viewModel";
import type {
  EnergyTrendSplitView,
  PanelEnergyPowerViewModel,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/types";

/* ── Family A: panel-overview aggregate frame → full view-model ───────────────
 * Wrap the raw ems_backend aggregate-envelope frame into the `socket` shape the
 * page's own mapper expects ({ state: AggregateState, status }). The mapper only
 * reads state.widgets / state.pending / state.hasSnapshot. One frame drives all
 * four cards (the live hook keys 4 sockets to the same endpoint; we share one). */
export function liveViewModel(frame: any): PanelEnergyPowerViewModel {
  const widgets = (frame && typeof frame === "object" && frame.widgets) || frame || {};
  const socket: any = {
    state: {
      mfmType: null,
      page: null,
      ts: null,
      widgets,
      layout: null,
      hasSnapshot: true,
      pending: false,
      pendingNote: null,
      lastError: null,
    },
    status: "open" as const,
  };
  const snapshot = mapPanelEnergyPowerAggregateToSnapshot(socket);
  if (!snapshot) throw new Error("energy-power frame not mappable");
  return createPanelEnergyPowerViewModel(snapshot);
}

/** Resolve one card's view: live (mapped from the frame) when available + mappable, else the payload default.
 *  `pick` selects the per-card view off the full live view-model. */
export function resolveView<V>(
  fallback: V,
  frame: any,
  pick: (vm: PanelEnergyPowerViewModel) => V,
  hasData: (v: V) => boolean,
): V {
  if (frame) {
    try {
      const v = pick(liveViewModel(frame));
      if (v && hasData(v)) return v;
    } catch {
      /* unmappable / empty frame → fall through to the payload default */
    }
  }
  // Fallback (seed) ONLY if it carries the data the card indexes. Layer 2 elides the data leaves, so a trend/demand seed
  // often lacks its `points` array → the card would crash on `.flatMap(undefined)`. null → the card returns a placeholder
  // ("no data") instead of a red render error when the live frame is missing/empty (e.g. a tunnel hiccup).
  return fallback && hasData(fallback) ? fallback : (null as unknown as V);
}

export const asSplit = (value: EnergyTrendSplitView): EnergyTrendSplitView =>
  value === "equipment" ? "equipment" : "total";

// This fill reads the LIVE aggregate (widgets) frame — "one frame drives all". But Layer 2 binds the trend/cumulative/
// demand cards to history endpoints (buckets shape), which this mapper can't read. Prefer the page's live frame (which
// carries cumulative/energy_trend/demand_profile in widgets) whenever the card's own frame isn't a widgets frame.
export const widgetsFrame = (frame: any, pageFrame: any): any =>
  (frame && typeof frame === "object" && (frame as any).widgets) ? frame : (pageFrame ?? frame);
