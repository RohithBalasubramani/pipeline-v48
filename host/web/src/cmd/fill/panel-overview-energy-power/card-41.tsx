import React from "react";
import { InputOutputEnergyCard } from "@cmd-v2/pages/electrical/tabs/energy-power/InputOutputEnergyCard";

// Card 41 — Input vs Output Energy card (equipment-detail tab). story render: probe(args.data) →
//   <InputOutputEnergyCard data/>. Same seed-degrade reasoning as card 40.
export const card41 = (payload: any): React.ReactNode => {
  const data = payload?.data ?? payload;
  if (!data) return null;
  return <InputOutputEnergyCard data={data} />;
};
