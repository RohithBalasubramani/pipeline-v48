// FILL module (thin barrel) for page panel-overview-shell/voltage-current.
//
// ATOMISED: each card render fn lives in a single-purpose file under ./panel-overview-voltage-current/,
// with shared honest-empty view-model helpers (view-model.ts) and card-18 date-wiring (date-wiring.ts)
// split by concern. This barrel re-exports the card_id-keyed CARDS registry the loader reads.
//
// PAYLOAD-DIRECT (ems_backend RETIRED — the host emits frames={} EMPTY): the ONLY data source is each
// card's Layer-2 completed `payload` (real neuract values + honest-blank '—', shaped as the CMD V2 card
// props). The old LIVE aggregate/column-row frame path (view-model.ts's panelVcViewModel + card-43's
// column-row reducer) is dead code now and was DELETED. Card 18's date/range/sampling control stays live
// (it emits onDateChange — a payload re-fetch, not a frame path).
//
// Cards 18-22 are the lt-pcc panel-overview Voltage&Current tab (EventsTopStrip + 4 cards). Card 43 is the
// equipment-detail tabs Voltage Health Summary card.
//
// The registry loads this via import.meta.glob("./fill/*.tsx") (single-level — the ./panel-overview-voltage-current/
// subfolder is NOT matched) and reads `m.CARDS`, so this file MUST keep exporting CARDS.

import React from "react";

import { card18 } from "./panel-overview-voltage-current/card-18";
import { card19 } from "./panel-overview-voltage-current/card-19";
import { card20 } from "./panel-overview-voltage-current/card-20";
import { card21 } from "./panel-overview-voltage-current/card-21";
import { card22 } from "./panel-overview-voltage-current/card-22";
import { card43 } from "./panel-overview-voltage-current/card-43";

/* CARDS registry — keyed by card_id. Each renders the Layer-2 completed payload's single slice
 * directly as the CMD V2 card props (the `frame` arg is ignored — frames are empty now). Card 18
 * additionally takes onDateChange for its live date control. */
export const CARDS: Record<number, (payload: any, frame?: any, onDateChange?: (dw: any) => void) => React.ReactNode> = {
  18: card18,
  19: card19,
  20: card20,
  21: card21,
  22: card22,
  43: card43,
};
