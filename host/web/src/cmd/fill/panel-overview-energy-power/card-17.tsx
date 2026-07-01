import React from "react";
import { DemandProfileCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/Cards";
import type { DemandProfileCardView } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/types";
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

// Card 17 — Daily Power Demand by Feeder card. story render: probe(args.demand) →
//   <DemandProfileCard view selectedLabel range sampling shift on*…/>
export const card17 = (
  payload: any,
  frame?: any,
  onDateChange?: (dw: DateWindow) => void,
  pageFrame?: any,
): React.ReactNode => {
  const demand = payload?.demand ?? payload ?? {};
  const view = resolveView<DemandProfileCardView>(
    demand.view,
    widgetsFrame(frame, pageFrame),
    (vm) => vm.demandProfile,
    (v) => Array.isArray(v?.points) && v.points.length > 0,
  );
  if (!view) return null;
  const range = (demand.range ?? "last-7") as EnergyTrendRangeOption;
  const sampling = (demand.sampling ?? "hourly") as EnergySamplingOption;
  const bind = makeWindowBinder(onDateChange, {
    range: trendRangeToWindowRange(range),
    sampling: samplingToWindowSampling(sampling),
  });
  return (
    <DemandProfileCard
      view={view}
      selectedLabel={demand.selectedLabel ?? null}
      range={range}
      sampling={sampling}
      shift={(demand.shift ?? "all") as EnergyShiftOption}
      onRangeChange={bind.onRangeChange}
      onSamplingChange={bind.onSamplingChange}
      onSelect={() => undefined}
    />
  );
};
