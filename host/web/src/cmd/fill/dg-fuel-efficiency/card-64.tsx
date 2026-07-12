import React from "react";
// Card 64 — All Runs (Fuel Log) (page diesel-generator-asset-dashboard/fuel-efficiency). The REAL RunsList (rendered
// through the shared DataTable primitive) rendered DIRECTLY from the Layer-2 payload {stats} — the payload IS the props.
//
// FRAMES=PAYLOADS [architecture]: host-served is RETIRED (frames={} EMPTY), so there is no live-frame / mapper path.
// The Layer-2 payload carries the `stats` slice (title + column labels + aggregates — real or honest-blank '—'); the
// DG start/run LOG is telemetry neuract does NOT carry, so there is no `runs` leaf on the payload → runs is always [].
// RunsList then renders its OWN empty state ("No runs in this period") under a real header — a correct blank tile,
// never a null card and never the seed 36-starts / 1626 L mock numbers.
// RunsList carries no per-card date control here — so no onDateChange.
import { RunsList } from "@cmd-v2/pages/assets/diesel-generator/tabs/fuel-efficiency/FuelHistoryCharts";
import type { FuelRun } from "@cmd-v2/pages/assets/diesel-generator/tabs/fuel-efficiency/types";
import { runsStats } from "./view-model";

// The run rows have NO neuract source on this page → always empty; RunsList draws its own emptyState under the header.
const NO_RUNS: FuelRun[] = [];

function RunsListFill({ payload }: { payload: any }) {
  // runsStats is ALWAYS a fully-labelled RunsStats (real from the payload, else zero-valued honest blank) — never null.
  return <RunsList runs={NO_RUNS} stats={runsStats(payload)} />;
}

export const card64 = (p: any): React.ReactNode => <RunsListFill payload={p} />;
