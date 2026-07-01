import React from "react";
// FILL: panel-overview-shell/energy-power — wire each card to its REAL CMD V2 component WITH live ems_backend data.
//
// THIN BARREL. Each card render fn + the shared helpers (view-model mapper, date-wiring, types) now live atomised in the
// sibling ./panel-overview-energy-power/ folder — the Vite registry glob is `./fill/*.tsx` (non-recursive: `*` does not
// cross `/`), so those folder files are NOT auto-loaded; only THIS barrel is, and it re-exports the CARDS registry.
//
// TWO card families live on this page:
//
//  A) Panel-overview cards 14/15/16/17 (Cards.tsx). Page recipe mirrors usePanelEnergyPowerData.ts:
//        frame ─► mapPanelEnergyPowerAggregateToSnapshot(socket) ─► snapshot ─► createPanelEnergyPowerViewModel(snap)
//                ─► vm.{cumulativeEnergy|livePower|energyTrend|demandProfile} ─► render the REAL card.
//     The card's own mapper reads socket.state.widgets; the host hands us the raw aggregate-envelope frame
//     ({ widgets, ts, ... }), so we wrap it in a synthetic socket exactly like the page hook does (see the
//     energy-distribution sibling fill). payload (exact_metadata) = the Storybook STORY ARGS:
//        card 14/15 = { variant, card:   { view, range, sampling, shift } }
//        card 16     = { variant, trend:  { view, selectedLabel, range, sampling, shift } }
//        card 17     = { variant, demand: { view, selectedLabel, range, sampling, shift } }
//     unwrapped exactly as storybook/EnergyPowerCards.stories.tsx does. The default view under
//     payload.<key>.view is the honest-degrade fallback when there is no live frame.
//
//  B) Equipment-detail tab cards 40/41 (tabs/energy-power). These take `data={...}` directly
//        card 40 = { variant, data: PowerEnergyAnalysisData }   → <PowerEnergyAnalysisChart data onPeriodChange/>
//        card 41 = { variant, data: InputOutputEnergyData }     → <InputOutputEnergyCard data/>
//     Their live mapper (mapEnergyPowerSocketsToSnapshot) needs a column-row LIVE socket + a separate history
//     socket AND explicitly bails ('unavailable') when mfmType === 'pcc_panel' — which this panel-overview page
//     IS. The host hands ONE aggregate-envelope frame per endpoint, not that two-socket column-row pair, so there
//     is no faithful live bridge for these on this page. They honest-degrade to the seed payload.data default.
import { card14 } from "./panel-overview-energy-power/card-14";
import { card15 } from "./panel-overview-energy-power/card-15";
import { card16 } from "./panel-overview-energy-power/card-16";
import { card17 } from "./panel-overview-energy-power/card-17";
import { card40 } from "./panel-overview-energy-power/card-40";
import { card41 } from "./panel-overview-energy-power/card-41";
import type { DateWindow } from "./panel-overview-energy-power/types";

export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: (dw: DateWindow) => void, pageFrame?: any) => React.ReactNode
> = {
  14: card14,
  15: card15,
  16: card16,
  17: card17,
  40: card40,
  41: card41,
};
