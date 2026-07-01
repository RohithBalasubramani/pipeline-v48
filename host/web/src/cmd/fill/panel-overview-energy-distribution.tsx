import React from "react";
// FILL: panel-overview-shell/energy-distribution — wire each card to its REAL CMD V2 component WITH live ems_backend data.
//
// Page recipe (mirrors useEnergyDistributionData.ts):
//   frame ─► mapAggregateSocketToSnapshot(socket) ─► snapshot ─► buildEnergyDistributionViewModel(...) ─► vm ─► render
// The card's own mapper (mapAggregateSocketToSnapshot) reads socket.state.widgets; the host hands us the raw aggregate
// envelope frame ({ widgets, layout, ts, ... }), so we wrap it in a synthetic socket exactly like the page hook does.
//
// payload (exact_metadata) = the Storybook STORY ARGS. Card 12 = { variant, rail: { vm, selectedNodeId } };
// card 13 = { variant, flow: { vm, selectedNodeId } } — unwrapped exactly as EnergyDistributionCards.stories.tsx does.
// The default vm under payload.rail.vm / payload.flow.vm is the honest-degrade fallback when there's no live frame.
import { EnergyInputDistributionCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/EnergyInputDistributionCard";
import { EnergyFlowDiagramCard } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/EnergyFlowDiagramCard";
import { mapAggregateSocketToSnapshot } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/mapper";
import { buildEnergyDistributionViewModel } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/viewModel";
import {
  SOURCE_CONFIGS,
  CONSUMER_CATEGORIES,
} from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/config";
import type { EnergyDistributionViewModel } from "@cmd-v2/pages/electrical/lt-pcc/panel-overview/energy-distribution/types";

/** Wrap the raw ems_backend aggregate-envelope frame into the `socket` shape the page's own mapper expects
 *  ({ state: AggregateState, status }). The mapper only reads state.widgets / state.pending / state.pendingNote. */
function liveVm(frame: any): EnergyDistributionViewModel {
  const widgets = (frame && typeof frame === "object" && frame.widgets) || frame || {};
  const socket: any = {
    state: {
      mfmType: null,
      page: null,
      ts: null,
      widgets,
      layout: null,
      hasSnapshot: true,
      pending: false,
      pendingNote: null,
      lastError: null,
    },
    status: "open" as const,
  };
  const snapshot = mapAggregateSocketToSnapshot(socket);
  return buildEnergyDistributionViewModel({
    incomingRows: snapshot.incomingRows,
    panelRows: snapshot.panelRows,
    mainMeter: snapshot.mainMeter,
    sourceConfigs: SOURCE_CONFIGS,
    consumerCategories: CONSUMER_CATEGORIES,
    reconciledLoss: snapshot.reconciledLoss,
    // API mode: never let stale static nameplates manufacture utilization (mirrors useEnergyDistributionData).
    useStaticNameplateFallback: false,
    aiSummaryText: snapshot.aiSummaryText,
  });
}

/** A vm is RENDERABLE only if it carries the arrays EnergyInput/FlowDiagram map over (sources/consumers). */
function hasRows(vm: any): boolean {
  return !!vm && (vm.sources?.length || vm.consumers?.length);
}

/** Resolve the card's view-model: live (mapped from the frame) when available + mappable, else the payload default.
 *  Returns null when NEITHER the live frame NOR the seed default carries distribution rows — the caller then shows a
 *  placeholder instead of mounting the card with an empty vm (which crashes on `vm.sources.map(...)`). [guard] */
function resolveVm(inner: any, frame: any): EnergyDistributionViewModel | null {
  if (frame) {
    try {
      const vm = liveVm(frame);
      // Only adopt the live vm if the frame actually carried distribution rows; an empty/loading frame yields a
      // degenerate vm (no sources/consumers) and we'd rather show the seed default than an empty card.
      if (hasRows(vm)) return vm;
    } catch {
      /* unmappable frame → fall through to the payload default */
    }
  }
  const fallback = inner?.vm as EnergyDistributionViewModel;
  return hasRows(fallback) ? fallback : null;   // guard: never hand the card a vm without the arrays it maps over
}

export const CARDS: Record<number, (payload: any, frame?: any) => React.ReactNode> = {
  // Card 12 — Energy Input & Distribution rail. story render: probe(args.rail) → <EnergyInputDistributionCard vm selectedNodeId onToggleNode/>
  12: (payload, frame) => {
    const rail = payload?.rail ?? payload ?? {};
    const vm = resolveVm(rail, frame);
    if (!vm) return null;
    // EnergyInputDistributionCard maps BOTH vm.sources and vm.consumers (+ nested
    // group.meters). The elided-seed fallback can carry one array but drop the
    // other; hasRows()'s OR would still pass, then vm.consumers.map(...) / the
    // missing array crashes. Require both arrays before mounting. [guard]
    if (!Array.isArray(vm.sources) || !Array.isArray(vm.consumers)) return null;
    return (
      <EnergyInputDistributionCard
        vm={vm}
        selectedNodeId={rail.selectedNodeId ?? null}
        onToggleNode={() => undefined}
      />
    );
  },

  // Card 13 — Energy Flow Diagram. story render: probe(args.flow) → <EnergyFlowDiagramCard vm selectedNodeId onNodeClick/>
  13: (payload, frame) => {
    const flow = payload?.flow ?? payload ?? {};
    const vm = resolveVm(flow, frame);
    if (!vm) return null;
    // EnergyFlowDiagramCard does NOT read vm.sources/vm.consumers — it maps
    // vm.sankey.nodes (StageHeaderRow: Math.max(...vm.sankey.nodes.map) + FlowSankey
    // computeLayoutD3 reads data.nodes/data.links) and vm.legend (SankeyLegend maps
    // groups + group.items), and reads vm.kpis.band scalars. hasRows() only checks
    // sources/consumers, so the elided seed can pass it yet still drop sankey/legend/
    // kpis. Guard the exact arrays this card iterates. [guard]
    if (
      !vm.sankey ||
      !Array.isArray(vm.sankey.nodes) ||
      !Array.isArray(vm.sankey.links) ||
      !Array.isArray(vm.legend) ||
      !vm.kpis
    )
      return null;
    return (
      <EnergyFlowDiagramCard
        vm={vm}
        selectedNodeId={flow.selectedNodeId ?? null}
        onNodeClick={() => undefined}
      />
    );
  },
};
