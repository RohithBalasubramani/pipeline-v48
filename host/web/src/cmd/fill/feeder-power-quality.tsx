import React from "react";
// FILL module — page individual-feeder-meter-shell/power-quality. THIN BARREL: one render fn per card_id lives in the
// sibling ./feeder-power-quality/ folder (card-<id>.tsx). FRAMES ARE RETIRED: each renders the REAL CMD V2 component
// DIRECTLY from the Layer-2 completed payload (real neuract values + honest-blank), guarded + injecting the tab's real
// sampling chrome for the two rail charts (see ./feeder-power-quality/date-window.ts, sampling.ts). Honest-degrade: a
// payload with no usable slice renders CMD V2's OWN structured-empty view-model — never throws, never a seed. The
// registry loads this file via import.meta.glob("./fill/*.tsx") and reads `CARDS`, so the barrel MUST keep the same
// base name + export CARDS.
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
