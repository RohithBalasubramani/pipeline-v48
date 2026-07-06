import React from "react";
// Card 41 — Input vs Output Energy (page individual-feeder-meter-shell/energy-power). FRAMES ARE RETIRED: the ONLY data
// source is the Layer-2 completed payload (`{ variant, data: InputOutputEnergyData }` — real neuract HV/LV +
// honest-blank). InputOutputEnergyCard reads hvInputKw/lvOutputKw/lossKwh/efficiencyPct PLAINLY and `.toLocaleString()`s
// them (NO guard), so `inputOutputData` forces those five numeric leaves finite (honest-blank → 0) while keeping every
// label/unit/colour byte-identical, and falls back to a fully-numeric zero-kW card when the slice is absent. The card
// STILL DRAWS, never a blank/null card and never a fabricated seed. NO date/range control → no onDateChange.
import { InputOutputEnergyCard } from "@cmd-v2/pages/electrical/tabs/energy-power/InputOutputEnergyCard";
import { inputOutputData } from "./view-model";

function InputOutputFill({ payload }: { payload: any }) {
  const data = inputOutputData(payload); // never null, fully numeric + labelled
  return <InputOutputEnergyCard data={data} />;
}

export const card41 = (p: any): React.ReactNode => <InputOutputFill payload={p} />;
