import React from "react";
import { EnergyTrendCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/Cards";
import type { EnergyTrendCardView } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/types";
import type {
  EnergySamplingOption,
  EnergyShiftOption,
  EnergyTrendRangeOption,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-power/config";
import { asSplit, resolveView, widgetsFrame } from "./viewModel";
import {
  makeWindowBinder,
  samplingToWindowSampling,
  trendRangeToWindowRange,
} from "./dateWiring";
import type { DateWindow } from "./types";

// Card 16 — Energy Consumption Trend card. story render: probe(args.trend) →
//   <EnergyTrendCard view={{...view, splitView}} selectedLabel range sampling shift on*…/>
export const card16 = (
  payload: any,
  frame?: any,
  onDateChange?: (dw: DateWindow) => void,
  pageFrame?: any,
): React.ReactNode => {
  const trend = payload?.trend ?? payload ?? {};
  const view = resolveView<EnergyTrendCardView>(
    trend.view,
    widgetsFrame(frame, pageFrame),
    (vm) => vm.energyTrend,
    (v) => Array.isArray(v?.points) && v.points.length > 0,
  );
  if (!view) return null;
  const range = (trend.range ?? "last-7") as EnergyTrendRangeOption;
  const sampling = (trend.sampling ?? "hourly") as EnergySamplingOption;
  const bind = makeWindowBinder(onDateChange, {
    range: trendRangeToWindowRange(range),
    sampling: samplingToWindowSampling(sampling),
  });
  return (
    <EnergyTrendCard
      view={{ ...view, splitView: asSplit(view.splitView) }}
      selectedLabel={trend.selectedLabel ?? null}
      range={range}
      sampling={sampling}
      shift={(trend.shift ?? "all") as EnergyShiftOption}
      onRangeChange={bind.onRangeChange}
      onSamplingChange={bind.onSamplingChange}
      onSelect={() => undefined}
      onSplitChange={() => undefined}
    />
  );
};
