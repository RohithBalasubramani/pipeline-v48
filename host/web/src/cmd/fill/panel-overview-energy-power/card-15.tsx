import React from "react";
import { EnergyProgressCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/Cards";
import type { EnergyProgressCardView } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/types";
import type {
  EnergySamplingOption,
  EnergyShiftOption,
  EnergyTrendRangeOption,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/config";
import { resolveView, widgetsFrame } from "./viewModel";
import {
  makeWindowBinder,
  samplingToWindowSampling,
  trendRangeToWindowRange,
} from "./dateWiring";
import type { DateWindow } from "./types";

// Card 15 — Today Live Power Analysis progress card. Same component as 14, fed the livePower view.
export const card15 = (
  payload: any,
  frame?: any,
  onDateChange?: (dw: DateWindow) => void,
  pageFrame?: any,
): React.ReactNode => {
  const card = payload?.card ?? payload ?? {};
  const view = resolveView<EnergyProgressCardView>(
    card.view,
    widgetsFrame(frame, pageFrame),
    (vm) => vm.livePower,
    (v) => Array.isArray(v?.metrics) && v.metrics.length > 0,
  );
  if (!view) return null;
  const range = (card.range ?? "today") as EnergyTrendRangeOption;
  const sampling = (card.sampling ?? "hourly") as EnergySamplingOption;
  const bind = makeWindowBinder(onDateChange, {
    range: trendRangeToWindowRange(range),
    sampling: samplingToWindowSampling(sampling),
  });
  return (
    <EnergyProgressCard
      view={view}
      range={range}
      sampling={sampling}
      shift={(card.shift ?? "all") as EnergyShiftOption}
      onRangeChange={bind.onRangeChange}
      onSamplingChange={bind.onSamplingChange}
    />
  );
};
