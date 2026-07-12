# PRIM port contract — primitives-only render path (2026-07-12)

USER DIRECTIVE: **no page cards** — the host mounts CMD_V2 chart PRIMITIVES directly from each card's
completed payload. Header, legends, colors, values: everything presentational rides the payload (AI-morphable);
the host adapter is only the payload→primitive mapping. CMD_V2 source is READ-ONLY.

## Rules (binding for every family file)

1. **Imports**: ONLY from `@cmd-v2/components/charts/primitives` (the barrel). NEVER from `@cmd-v2/pages/**`.
   The barrel is rich — BodyCard, Card, CardHeader, DataTable, MetricTileGrid, EventTimelineChart,
   RadarChart, ComparisonRadarChart, CompositeChartCard, ChartFrame/GridAxis/LinePath/StackedBars/ChartBars,
   HorizontalBand/ReferenceLine/EventDot, KpiStatStrip, FillBar, TickProgressBar, SegmentedArcGauge,
   StatusBadge/StatusPill, AiSummary, SegmentBar, EventStripControls, FlowSankey, SankeyLegend, EfficiencyBand,
   SpectrumBar, InteractiveLegendRow, SamplingPicker?, SegmentedControl, Skeleton, LiveTag, DonutChart,
   PhaseValueRows, KpiMiniCard, useInteractiveLegend, resolveEventFilter … If a visual truly has no barrel
   equivalent (e.g. the DG 3D fuel tank), render an honest placeholder card (BodyCard + note) — never import
   the page component, never hand-draw.
2. **Shape**: each family file exports `CARDS: Record<number, (payload: any, onDateChange?: (dw:any)=>void) => React.ReactNode>`.
   `prim/index.ts` merges them. The payload arg is the card's completed payload (post guard/forceBlank).
3. **Generic before specific**: use the shared adapters in `prim/shared.tsx` (tiles/table/timeline/radar/
   kpi-strip/ai/line-history/title) wherever the payload's pres vocabulary fits; add family-local mapping
   only for what shared cannot express. NO closed accessor records keyed by semantic field names — series/
   columns/tiles are looked up from the payload by key (`(p) => p[key]`), with per-family DEFAULT alias maps
   as DATA constants when a legacy pres id ≠ row field (e.g. table col `voltage` → row `vAvg`).
4. **Honesty**: never fabricate. A missing list renders empty chrome; a missing scalar renders `'—'` via
   `fin()/dash()` from shared. NO view-model builders that seed synthetic points/zero rows. Tone/color record
   lookups MUST have safe fallbacks (unknown tone → neutral), never a record-miss crash.
5. **Interactions**: local selection state via useState in the adapter; date controls via shared
   `useStripDateControl`/`SamplingPicker` wiring calling `onDateChange` (see `prim/date-wiring.ts`).
   `loading` prop (guard g16) → render `CardBodySkeleton`-equivalent from the barrel (Skeleton) with chrome.
6. **Titles**: `cardTitle(pres, period)` from shared handles `${titlePrefix}${titleConnector}${period.label}`;
   otherwise the payload's own title string (`data.title` / `view.title` / `vm.title` / `pres.title`), dashed
   when absent.
7. **Verification (mandatory before you finish)**: `cd host/web && npm run ssr-gate -- '../../outputs/prim_corpus/<your pages>.json'`
   must show YOUR cards `rendered OK` (the gate routes through PRIM automatically once your file is merged in
   prim/index.ts — add your import there). 0 THROW, 0 NULL-with-payload for your ids.
8. **Atomic structure**: one family file; extract a sub-widget to its own file under `prim/` if it exceeds
   ~80 lines. Comment only non-obvious constraints.

## Family file assignments

| file | card ids | corpus pages |
|---|---|---|
| prim/vc-events.tsx | 18,19,20,21,22,43 | panel-overview-shell_voltage-current |
| prim/pq.tsx | 23,24,25,26,27 | panel-overview-shell_harmonics-pq |
| prim/rtm.tsx | 7,9,10,11,36,37,38,6?,160? | panel-overview-shell_real-time-monitoring, individual-feeder-meter-shell_real-time-monitoring |
| prim/energy.tsx | 5,12,13,14,15,16,17,39,40,41,42 | panel-overview-shell_energy-power, panel-overview-shell_energy-distribution, individual-feeder-meter-shell_energy-power |
| prim/health-history.tsx | 44,45,46,66,67,68,69 | individual-feeder-meter-shell_voltage-current, diesel-generator-asset-dashboard_voltage-current |
| prim/ups.tsx | 50-59 | ups-asset-dashboard_* |
| prim/dg.tsx | 61,62,63,64,65,70,71,72,73 | diesel-generator-asset-dashboard_* |
| prim/transformer.tsx | 74-81 | transformer-asset-dashboard_* |
| prim/pq-feeder.tsx | 47,48,49 | individual-feeder-meter-shell_power-quality |

The per-family payload vocabularies + closed-vocab lists are in `docs/primitives_inventory/<family>.md` —
READ YOURS FIRST; it names every payload path your cards carry.
