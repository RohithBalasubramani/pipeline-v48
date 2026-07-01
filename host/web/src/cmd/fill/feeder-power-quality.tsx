import React from "react";
// FILL module — page individual-feeder-meter-shell/power-quality. THIN BARREL: one render fn per card_id lives in the
// sibling ./feeder-power-quality/ folder (card-<id>.tsx), each rendering the REAL CMD V2 component fed (a) the card's
// exact_metadata payload AND (b) the LIVE ems_backend frame, mapped via THIS page's OWN CMD V2 mappers/builders
// (see ./feeder-power-quality/mappers.ts, guards.ts, date-window.ts, sampling.ts). Honest-degrade: a missing/unmappable
// frame renders from the payload's default data — never throws. The registry loads this file via
// import.meta.glob("./fill/*.tsx") and reads `CARDS`, so the barrel MUST keep the same base name + export CARDS.
import { card47 } from "./feeder-power-quality/card-47";
import { card48 } from "./feeder-power-quality/card-48";
import { card49 } from "./feeder-power-quality/card-49";

export const CARDS: Record<
  number,
  (payload: any, frame?: any, onDateChange?: (dw: any) => void) => React.ReactNode
> = {
  47: card47,
  48: card48,
  49: card49,
};
