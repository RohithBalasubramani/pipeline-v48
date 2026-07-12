# Panel-Overview Card Family — Primitives Inventory (for a primitives-only render port)

Scope: cards 7, 9–27 (barrel `host/web/src/cmd/components/panel-overview.ts`), the fill barrels
that shadow them, and every distinct CMD_V2 page-card component they mount
(CMD_V2 root `/home/rohith/CMD_V2/src`, `@cmd-v2` alias). Written 2026-07-12.

Render precedence (host `src/cmd/registry.tsx`): **SPECIAL → FILL → COMPONENTS → COMPOSE → HonestBlank**.
FILL[id] deliberately WINS over COMPONENTS[id] ("letting COMPONENTS shadow FILL bypassed every guard").

---

## 1. card_id → CMD_V2 component (COMPONENTS barrel)

File: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/host/web/src/cmd/components/panel-overview.ts`
All paths below are under `/home/rohith/CMD_V2/src/pages/electrical/lt-pcc/panel-overview/`.

| card_id | Component export | Source file | Note |
|---|---|---|---|
| 7  | `RealTimeMonitoringRail` | `realtime-monitoring/RealTimeMonitoringRail.tsx` | rail composite (AI + supply + trend + quick-stats) |
| 9  | `SupplyCard` | `realtime-monitoring/RealTimeMonitoringRailCards.tsx` | |
| 10 | `TrendCard` | `realtime-monitoring/RealTimeMonitoringRailCards.tsx` | |
| 11 | `QuickStats` | `realtime-monitoring/RealTimeMonitoringRailCards.tsx` | |
| 12 | `EnergyInputDistributionCard` | `energy-distribution/EnergyInputDistributionCard.tsx` | |
| 13 | `EnergyFlowDiagramCard` | `energy-distribution/EnergyFlowDiagramCard.tsx` | sankey |
| 14 | `EnergyProgressCard` | `energy-power/Cards.tsx` | same component as 15 |
| 15 | `EnergyProgressCard` | `energy-power/Cards.tsx` | duplicate binding |
| 16 | `EnergyTrendCard` | `energy-power/Cards.tsx` | |
| 17 | `DemandProfileCard` | `energy-power/Cards.tsx` | |
| 18 | `EventsTopStrip` | `voltage-current/EventsTopStrip.tsx` | SHADOWED by fill |
| 19 | `AiSummaryCard` | `voltage-current/Cards.tsx` | SHADOWED by fill |
| 20 | `withSectionSplit(EventTimelineCard)` | `voltage-current/Cards.tsx` + host `src/cmd/section-split.tsx` | SHADOWED by fill (fill also wraps) |
| 21 | `CurrentDistributionCard` | `voltage-current/Cards.tsx` | SHADOWED by fill |
| 22 | `OtherPanelsTable` | `voltage-current/Cards.tsx` | SHADOWED by fill |
| 23 | `PqTopStrip` | `harmonics-pq/HarmonicsPqTab.tsx` | SHADOWED by fill |
| 24 | `PqTimelineCard` | `harmonics-pq/HarmonicsPqTab.tsx` | SHADOWED by fill |
| 25 | `PqAiSummaryCard` | `harmonics-pq/HarmonicsPqTab.tsx` | SHADOWED by fill |
| 26 | `PqFeederTable` | `harmonics-pq/HarmonicsPqTab.tsx` | SHADOWED by fill |
| 27 | `SignatureCard` | `harmonics-pq/HarmonicsPqTab.tsx` | SHADOWED by fill |

## 2. FILL overlap (FILL shadows COMPONENTS at render time)

Checked ALL `fill/*.tsx` CARDS keys: 36–38, 39–42, 44–46, 47–49, 61–81 (dg/feeder/transformer families),
plus the two below. **Cards 7 and 9–17 have NO fill overlap** — they render via COMPONENTS directly.

### `fill/panel-overview-voltage-current.tsx` → serves cards **18, 19, 20, 21, 22** (+43, outside this family)
Per-card fns in `fill/panel-overview-voltage-current/card-NN.tsx`; shared honest-empty helpers in
`view-model.ts` (re-uses CMD_V2's own `createPanelVoltageCurrentViewModel`/`periodStats`/`buildVcPresentation`)
and `date-wiring.ts`. Payload slice per card (the fn then mounts the SAME CMD_V2 component as §1):

| card | fill fn | payload slice → component props |
|---|---|---|
| 18 | `card18` | `p.strip` → `{pres, stats, timeChoice, timeOptions, filterSelection…}`; takes `onDateChange` (live re-fetch) |
| 19 | `card19` | `p.summary` + real narrative `p.ai_summary?.text ?? p.widgets?.ai_summary?.text` injected as `pres.backendHeadline` |
| 20 | `card20` | `p.trend` → `{period, points, selectedLabel}`; **also** wraps in `withSectionSplit(EventTimelineCard)` |
| 21 | `card21` | `p.distribution` → `{pres, period, selectedPanelId}` |
| 22 | `card22` | `p.table` → `{pres, period, mode, selectedPanelId}` |

Guarantee pattern: payload leaf missing → backfill from the page's OWN honest-empty view-model
(chrome-only, zero fabrication), never null. Old live-frame path DELETED.

### `fill/panel-overview-harmonics-pq.tsx` → serves cards **23, 24, 25, 26, 27**
Per-card fns in `fill/panel-overview-harmonics-pq/card-NN.tsx` + `date-window.ts`/`derive.ts`/`noop.ts`.

| card | fill fn | payload slice |
|---|---|---|
| 23 | `renderTopStrip` | `payload.strip = {pres, filterSelection, …}`; date control live via `onDateChange` |
| 24 | `renderTimeline` | `payload.timeline = {pres, limits, periods, …}` |
| 25 | `renderAiSummary` | `payload.summary = {pres, period, focus, stats, …}` |
| 26 | `renderFeederTable` | `payload.table = {pres, period, selectedPanelId}` |
| 27 | `renderSignature` | `payload.signature = {pres, period, selectedPanelId, …}` |

Missing periods degrade to `derive.ts` honest-empty builders (`emptyPeriod`/`emptyPeriodWithRow`/`emptyStats`).

---

## 3. Per-component inventory

Primitive imports are from `/home/rohith/CMD_V2/src/components/charts/primitives` unless noted.

### 3.1 `RealTimeMonitoringRail` (card 7)
`realtime-monitoring/RealTimeMonitoringRail.tsx`
- **Primitives**: `Card` (fixed `w-[300px]` rail) → `CardHeader` (composed title node + `RailStatusPill` in `action` slot) → vertical stack of `AiSummary(density="compact")`, `SupplyCard`, `TrendCard`, `QuickStats` (the card-9/10/11 components inlined). `ListBodySkeleton rows={4}` when `availability==='loading'`.
- **Payload → primitive**: one prop `railVM: RailViewModel` — `railVM.title/subtitle/statusBadge` → header; `railVM.aiSummaryText` → AiSummary; `railVM.supply/.trend/.quickStats/.quickStatsLayout` → the three sub-cards.
- **Closed vocab**: none of its own (delegates to sub-cards). `availability` union `'loading'|'partial'|'ready'|'unavailable'`.
- **State/interactions**: stateless; optional `onClear` renders a back-chevron `BackButton`.
- **Title**: `railVM.title` (+ optional `railVM.subtitle`), pill from `railVM.statusBadge`.

### 3.2 `SupplyCard` / `TrendCard` / `QuickStats` (cards 9 / 10 / 11)
`realtime-monitoring/RealTimeMonitoringRailCards.tsx`
- **Primitives**: local `RailCard` chrome (SURFACES.card section). SupplyCard = hand-built headline + segment bar (`supply.breakdown[].{value,color,label,unit}` → `width:%` spans) + legend rows; TrendCard = **hand-drawn inline SVG sparkline** (`<path>` area+line + `<circle>` dots — NOT a primitive) + bottom-stat strip; QuickStats = `KpiMiniCard` per tile (2-col grid or stack via `layout`). Shared `RailStatusPill` → DS `StatusPill`; text composed via `composeMetricText`/`composeValueUnit`.
- **Payload → primitive**:
  - Supply: `supply.value / supply.denominator supply.unit` headline (`fmt(supply.value,0)` + `/ composeValueUnit(fmt(supply.denominator,0), supply.unit)`); `supply.delta` (MetricText) + `deltaColor/deltaGlyph`; `supply.consumedHint.{consumedPct,leftKw,consumedLabel,leftLabel,percentUnit}`; `supply.breakdown[]` drives both the proportional bar and the legend.
  - Trend: `trend.series: number[]` → sparkline points (`x = i/(n-1)*270`, `y` min/max normalized, h=44); `trend.lineColor ?? TOKENS.graph.purple500`, `trend.areaOpacity ?? 0.15`; `trend.bottomStats[].{label,value,unit,subtext,trend{dir,label,color,glyph}}`; `trend.statusBadge` pill.
  - QuickStats: `stats[].{label,value,unit,trend{dir,label,color,glyph},status}` → `KpiMiniCard{label,value,unit,trend,trendSlot}`.
- **Closed vocab**: `RAIL_TONE_TO_DS: Record<Tone, StatusPillTone> = {success:'normal', warning:'alarm'}` (Tone union `'success'|'warning'`); `RT_DIR_PRESETS: Record<'up'|'down'|'flat', {color,glyph:'↑'|'↓'|'→'}>` — dir union is CLOSED, but color/glyph are payload-overridable (`?? preset` fallback). Badge word precedence `badge.text || badge.vocab?.[badge.key] || badge.label`.
- **State/interactions**: fully stateless (pure functions of props).
- **Title**: `supply.title` / `trend.title` inline headers (fontSerif warm700); QuickStats has no header.

### 3.3 `EnergyInputDistributionCard` (card 12)
`energy-distribution/EnergyInputDistributionCard.tsx`
- **Primitives**: `Card` → `CardHeader` → scrollable list of tab-local rows: `RailRow` (label + kWh + utilization bar), `RailSectionHeader` (uses `composeMetricHeader`), `RailGroupHeader`, `RailTotalRow` (uses `composeValueUnit`). `ListBodySkeleton rows={8}` while loading. No chart primitive — it is a hierarchical list/rail.
- **Payload → primitive**: `vm: EnergyDistributionViewModel` — `vm.allRowLabel/allTotalKwh/allUtilizationPct/allRowColor` → "All" row; `vm.sourcesSection.{groupLabel,columnHeader}` + `vm.sources[].{id,label,totalKwh,utilizationPct,color,meters[]}`; `vm.supplied.{label,unit}` + `vm.totalSuppliedKwh`; `vm.consumersSection.*` + `vm.consumers[].{id,label,totalKwh,utilizationPct,color,meters[].{id,label,kwh,utilizationPct}}`; `vm.consumed.*` + `vm.totalConsumedKwh`. Values formatted by `fmtKwh`.
- **Closed vocab**: sankey node-id CONVENTIONS hard-coded — `consumerNodeId = "meter-"+meterId`, `incomerNodeId = "incomer-"+incomerId` ("Must match viewModel.ts"). Source-group click always spotlights `src.meters[0]` (first incomer).
- **State/interactions**: controlled selection — `selectedNodeId: string|null` + `onToggleNode(nodeId)`; rows highlight when their computed nodeId matches. Selection is SHARED with card 13's sankey (host must lift this state to pair them).
- **Title**: `vm.inputCardTitle`.

### 3.4 `EnergyFlowDiagramCard` (card 13)
`energy-distribution/EnergyFlowDiagramCard.tsx`
- **Primitives**: `Card` → `CardHeader` → `AiSummary` + tab-local `KpiRibbon` (mounts primitive `EfficiencyBand`) + local `StageHeaderRow` + **`FlowSankey`** + **`SankeyLegend`**. `CardBodySkeleton kpiCells={3} legendRows={2}` while loading.
- **Payload → primitive**: `vm.aiSummary` → AiSummary; `vm.kpis` → KpiRibbon; `vm.sankey = {nodes[.layer/.stageTitle/.value], links}` (`FlowSankeyModel`) → `FlowSankey data`; `vm.stageUnit` → sankey `valueUnit` + stage header unit; `vm.legend: LegendGroup[]` → `SankeyLegend groups`. `StageHeaderRow` derives column count from `max(node.layer)+1` and prints `stageTitle` + `fmtKwh(node.value)` per layer.
- **Closed vocab**: none in JSX (node kinds live in the FlowSankey primitive types); node-id pairing with card 12 relies on the `meter-*`/`incomer-*` convention above.
- **State/interactions**: controlled `selectedNodeId` + `onNodeClick` (round-trips to the rail card).
- **Title**: `vm.flowCardTitle`.

### 3.5 `EnergyProgressCard` (cards 14, 15)
`energy-power/Cards.tsx`
- **Primitives**: `Card` → `CardHeader` (action = `SamplingPicker` [gated by `view.periodLabel`] + `StatusBadge`) → headline row (TYPOGRAPHY.progressHeadline*) → **`TickProgressBar`** → **`KpiStatStrip`** (round swatches, no dividers) → footer `AiSummary(compact)`. `CardBodySkeleton kpiCells={3}` while loading.
- **Payload → primitive**: `view.value/valueUnit/target/targetUnit` → headline (target renders as separate node — no fabricated "/1"); `view.markerLabel` (MetricText) → right meta; `view.segments[].{id,color,value}` + `view.capacityValue`/`view.capacityUsedValue` → `toTickSegments()` → TickProgressBar segments (+ synthetic `{id:'remaining', color:CHART_COLORS.cream300}` tail); `view.markerPct` → bar marker; `view.metrics[].{id,label,value,unit,sub,color}` → KpiStatStrip cells; `view.insight` → AiSummary; `view.statusLabel/statusTone` → StatusBadge; `view.rangeOptions/resolutionOptions/shiftOptions` → SamplingPicker rosters (payload-carried, AI-morphable).
- **Closed vocab**: `rangeOptionToPreset`/`presetToRangeOption` switch on the CLOSED `EnergyTrendRangeOption` union `'today'|'yesterday'|'last-7'|'this-month'|'last-month'|'custom'`; `selectionToBackendSampling` collapses to `sampling∈{'shift','hourly'}`, `shift∈{'a','b','c','all'}`.
- **State/interactions**: controlled date filter — props `range/sampling/shift/custom` + `onRangeChange/onSamplingChange` (the whole E&P tab shares one filter state).
- **Title**: `view.title` (plain string).

### 3.6 `EnergyTrendCard` (card 16)
`energy-power/Cards.tsx` + tab-local `energy-power/Charts.tsx`
- **Primitives**: `Card`/`CardHeader` (action = `SamplingPicker` + `SegmentedControl` split toggle) → local `TotalsStrip` (grid of per-bucket total pills) + chart (`EnergyStackedTrendChart` when `view.splitView==='total'` else `EnergyTotalStackedChart`) + right aside `ExpandableLegend(swatch="square", wrapLabels)` + `AiSummary(compact)`. Charts are tab-local but composed FROM primitives: `ChartFrame`, `GridAxis`, `ChartHoverCapture/Crosshair/Tooltip`, `ReferenceLine`-style dashed refs, hand-built stacked bar rects; `useInteractiveLegend` drives focus. `CardBodySkeleton rail railRows={4}` while loading.
- **Payload → primitive**: `view.points[]` (EnergyTrendPoint: `label, ups, bpdp, hhf, active, reactive, rated, contracted` **+ index signature `[feederId]: number`** — per-feeder values are flattened onto the point); `view.legend[]/{id,color,label,valueNumber,subRows[]}` — the roster: chart series are built generically as `value:(p)=>fieldOf(p, row.id)` so **series roster+order+color ride the payload**; `view.totals[].{label,value,tone}` → TotalsStrip (`tone==='warning'` → coral/warning wash); `view.totalLegend` for the active/reactive split view; `view.referenceLines` (id resolved off `points[0]` via `fieldOf`) → dashed refs; `view.yAxisTitle`, `view.totalLabel`, `view.baseRatio`, `view.insight`, `view.splitOptions/rangeOptions/resolutionOptions/shiftOptions`.
- **Closed vocab**: `view.splitView` binary `'total'|'equipment'` picks the chart component; the range/sampling unions of §3.5. The per-feeder series lookup is NOT closed (index-signature + roster).
- **State/interactions**: `useInteractiveLegend(legendKeys)` (legend click → dim others, includes subRow ids); controlled `selectedLabel` + `onSelect({kind:'period',label})` on bar click; controlled `range/sampling/shift/custom` + `onSplitChange`.
- **Title**: `view.title`.

### 3.7 `DemandProfileCard` (card 17)
`energy-power/Cards.tsx` + `Charts.tsx` (`FeederDemandLineChart`)
- **Primitives**: `Card`/`CardHeader` (action = `SamplingPicker`) → `KpiStatStrip` (local `DemandStats`: `view.stats[].{id,label,value,unit,sub}`) + `FeederDemandLineChart` (ChartFrame/GridAxis/LinePath/hover primitives; one line per `view.legend` row via generic `fieldOf(point, row.id)`; `view.criticalKw` soft reference) + aside `ExpandableLegend(swatch="line-plain")` + `AiSummary`. `CardBodySkeleton kpiCells={2} rail railRows={3}`.
- **Payload → primitive**: `view.points[]` (FeederDemandPoint: `label, ups, bpdp, hhf, [feederId]: number`), `view.legend[]` roster (+subRows), `view.stats`, `view.criticalKw`, `view.insight`, picker rosters.
- **Closed vocab**: range/sampling unions only; series lookup generic.
- **State/interactions**: `useInteractiveLegend`; `selectedLabel` + `onSelect`; controlled date filter props.
- **Title**: `view.title`.

### 3.8 `EventsTopStrip` (card 18)
`voltage-current/EventsTopStrip.tsx`
- **Primitives**: section chrome (not `Card`) containing `EventStripControls` (preset/resample/hour filter row) + **`SegmentBar`** + **`MetricTileGrid`** (7 tiles, HPQ-style selection).
- **Payload → primitive**: everything visual rides `pres: VcStripPresentation` (built by producer `buildVcPresentation`): `pres.segments[].{key,label,color}` + `pres.segmentOrder` → SegmentBar (`value` read off `stats[seg.key]`); `pres.tiles[].{key,label,swatch,color,payload,representsAll,unit,decimals}` + `pres.tileOrder` → MetricTileGrid items; `pres.controlsLeadingLabel`, `pres.controls.{presetOptions,resampleOptions,toLabel,byLabel,atLabel,ariaLabels.*}` → EventStripControls. Counts/pcts are DATA: `stats.total`, `stats[tile.key as EventMode]`, `stats.worstVoltage.vDeviation`, `stats.worstCurrent.iUnbalance`.
- **Closed vocab**: `tileItem()` switches on tile.key literals `'total'|'vDev'|'iImb'` else treats key as `EventMode`; `StripTileKey = 'total'|'sag'|'swell'|'current'|'neutral'|'vDev'|'iImb'`; `EventMode = 'sag'|'swell'|'current'|'neutral'`; segment `value: stats[seg.key]` requires seg.key ∈ EventMode. A payload cannot introduce a NEW tile/segment key — the stats accessor won't resolve.
- **State/interactions**: all controlled from the tab/fill: `preset/resample/timeChoice/timeOptions/customDate/rangeStart/rangeEnd` + 6 change callbacks; `selectedTileKey` + `onTileSelect(tileKey, payload)` (payload = EventMode for table filter, `'vDev'/'iImb'` for chart-line focus, null for total).
- **Title**: none (strip); leading caption = `pres.controlsLeadingLabel`.

### 3.9 `AiSummaryCard` (card 19)
`voltage-current/Cards.tsx`
- **Primitives**: **`BodyCard`** (title node = `pres.titleGlyph` + `pres.cardTitle`) → two labeled `AiSummary` blocks (TYPOGRAPHY.aiLabel headers `pres.aiLabel` / `pres.driversLabel`). `ListBodySkeleton rows={4}`.
- **Payload → primitive**: main text = `resolveVcAiHeadline(pres, period, mode, stats, selectedPanel)` — **`pres.backendHeadline` wins** (fill card-19 injects the executor narrative here), else local composition from `pres.vocab` + stats; drivers line = `` `${v.driversPrefix}${period.label}${v.driversSuffix}` ``.
- **Closed vocab**: `pres.vocab` sentence-fragment record (driversPrefix/driversSuffix etc.); `mode: EventMode` union.
- **State/interactions**: stateless.
- **Title**: `pres.titleGlyph + pres.cardTitle` (BodyCard).

### 3.10 `EventTimelineCard` (card 20) — sections-aware
`voltage-current/Cards.tsx`; timeline primitive at `voltage-current/EventTimelineChart.tsx` (typed re-export of the shared chart)
- **Primitives**: `BodyCard` → **`EventTimelineChart<EventTimelinePoint>`** (stack bars + overlay lines, legend, hover tooltip, point click). `CardBodySkeleton`.
- **Payload → primitive**: `points: EventTimelinePoint[]`; series rosters ride `pres`: `pres.stackSeries[].{key,label,color}` + `pres.stackOrder`, `pres.lineSeries[].{key,label,color,tileKey}` + `pres.lineOrder`, `pres.showLegend`, `pres.leftAxisLabel`, `pres.rightAxis.{label,unit,unitStyle}` (via `composeMetricHeader`), `pres.dimOpacity.{stack,line}`; x label = `p.label`.
- **Closed vocab (the sections-overlay gotcha)**: value accessors are HARD-CODED records —
  `stackValueFor: Record<TimelineStackKey,…> = { sag:p=>p.sag, swell:p=>p.swell, current:p=>p.current, neutral:p=>p.neutral }` and
  `lineValueFor = { vWorst:p=>Math.abs(p.vWorst), iWorst:p=>p.iWorst }`; `lineDim` keys on tileKey `'vDev'|'iImb'`.
  A payload with variant keys (e.g. `sag_a`/`sag_b`) yields `value: undefined` → chart crash. That is exactly why
  **both COMPONENTS and the fill wrap it in `withSectionSplit`** (host `src/cmd/section-split.tsx`): when the
  executor stamps `pres.sectionSplit: true`, a key-GENERIC re-implementation renders the same
  `EventTimelineChart` with `value: p => p[s.key]` accessors built from `pres.stackSeries/stackOrder/lineSeries/lineOrder`.
- **State/interactions**: controlled `selectedLabel` + `onPeriodSelect(label)` (point click); `selectedTileKey` from the strip drives per-series dim opacity.
- **Title**: `` `${pres.titlePrefix}${pres.titleConnector}${period.label}` ``.

### 3.11 `CurrentDistributionCard` (card 21)
`voltage-current/Cards.tsx`
- **Primitives**: `Card`/`CardHeader` → **`RadarChart`** + local rail (`CurrentDistributionRail`, plain divs). `CardBodySkeleton rail railRows={3}`.
- **Payload → primitive**: spokes from DATA: `period.panels.filter(p => p.amps != null && !isIncomerRow(p)).map(p => ({id, label: applyReplacements(p.panel, pres.spokeLabelReplacements), value: p.amps}))` — **outgoing feeders only** (incomer excluded via backend `role` or bay-label heuristic `isIncomerRow`); derived `total/average/peak` feed the rail; radar visual knobs all ride `pres.radar.{showPeakDot,polygonFill,polygonStroke,referenceFill,referenceStroke,peakColor,selectedColor}`; rail roster `pres.rail[].{key,label,color,dot}` + `pres.railOrder` + `pres.railDecimals` + `pres.unit`. Label sizing auto-ramps with spoke count (`radarSizing`, 8→24 spokes).
- **Closed vocab**: `RailKey = 'total'|'average'|'peak'` — `valueByKey` record; spoke value accessor fixed to `panel.amps`.
- **State/interactions**: `selectedPanelId` highlights a spoke (controlled; fill passes table selection default).
- **Title**: `` `${pres.titlePrefix}${pres.titleConnector}${period.label}` ``.

### 3.12 `OtherPanelsTable` (card 22)
`voltage-current/Cards.tsx`
- **Primitives**: `BodyCard` → **`DataTable<PanelPeriodState>`** (fillHeight, scrollBody, stickyHeader, stickyFirstColumn, row select). `ListBodySkeleton rows={6}`.
- **Payload → primitive**: rows = `period.panels`; columns from roster `pres.columns[].{id,header{label,unit,unitStyle},align,fit,unit,percentUnit,decimals}` + `pres.columnOrder`; the pseudo-column id `'events'` expands to one column per `pres.eventModeOrder` (or the single selected `mode`), header `` `${pres.eventColumn.shortByMode[m]} ${pres.eventColumn.descriptor}` ``, cell `panel[m]`; layout `pres.layout.{headerHeight,rowHeight,maxRowHeight}`, widths `pres.minWidth`/`pres.singleModeMinWidth`; selection/hover palette `pres.palette.{rowHoverBg,rowSelectedText,rowSelectedBg,rowSelectedBorder}`; label rewrite `pres.panelLabelReplacements`.
- **Closed vocab**: `tableColumn()` **switches on column id** — only `'panel'|'voltage'|'current'|'vDeviation'|'iUnbalance'|'cause'` (+ `'events'` handled above) have cell renderers; unknown id → `render: () => null`. Fixed data accessors: `panel.vAvg`, `panel.amps`, `panel.vDeviation`, `panel.iUnbalance`, `panel.cause || pres.causeVocab[panel.causeKey]`, `panel[m]` for m ∈ EventMode.
- **State/interactions**: controlled `selectedPanelId` + `onPanelSelect(id)` (row click); `mode: EventMode|null` from the strip narrows event columns.
- **Title**: `` `${pres.titlePrefix}${pres.titleConnector}${period.label}` ``.

### 3.13 `PqTopStrip` (card 23)
`harmonics-pq/HarmonicsPqTab.tsx`
- **Primitives**: section chrome → `EventStripControls` + `SegmentBar` + `MetricTileGrid` (structurally identical to card 18).
- **Payload → primitive**: `pres: HpqStripPresentation` — `pres.segments/segmentOrder` (value = `stats[seg.key]`), `pres.tiles/tileOrder` (`tileItem`), `pres.controlsLeadingLabel`, `pres.controls.*`. Data: `stats: PQStats` (`stats.total`, `stats[key as FocusKey]`, `stats.worstIThd.iThd`, `stats.worstVThd.vThd`); optional `windowWorst` (API-mode window peak) overrides worst-tile values.
- **Closed vocab**: `tileItem` switches on `'total'|'worstI'|'worstV'` else key as FocusKey; `StripTileKey = 'total'|'iThd'|'vThd'|'pfGap'|'neutral'|'worstI'|'worstV'`; `FocusKey = 'iThd'|'vThd'|'pfGap'|'neutral'`. Worst-tiles share `payload=focusKey` with their count twins (two entry points → one focus).
- **State/interactions**: controlled filter (`filterSelection`, `resolvedFilter` from primitive `resolveEventFilter`), `timeChoice/timeOptions`, `selectedTileKey` + `onTileSelect(tileKey, nextFocus)`, 6 filter callbacks. Fill card-23 keeps the date control LIVE via `onDateChange`.
- **Title**: none; caption `pres.controlsLeadingLabel`.

### 3.14 `PqTimelineCard` (card 24)
`harmonics-pq/HarmonicsPqTab.tsx`
- **Primitives**: `Card`/`CardHeader` → **`EventTimelineChart<PqTimelinePoint>`**. `CardBodySkeleton`.
- **Payload → primitive**: points DERIVED in-card: `periods.map(p => periodStats(p, limits))` → `{label, iThd, vThd, pfGap, neutral, worstI, worstV}` (so the card needs `periods: PQPeriod[]` + `limits: HpqLimits` threshold block, not pre-baked points); series roster/colour/order/axis labels/dim opacities all from `pres.{stackSeries,stackOrder,lineSeries,lineOrder,showLegend,leftAxisLabel,rightAxis,dimOpacity}`.
- **Closed vocab**: accessor records `stackValueFor: Record<FocusKey,…>` (iThd/vThd/pfGap/neutral) and `lineValueFor: Record<'worstI'|'worstV',…>`; dim pairing `lineFocusOf = {worstI:'iThd', worstV:'vThd'}`. Same variant-key crash class as card 20 (no section-split wrapper here).
- **State/interactions**: controlled `selectedLabel` + `onPeriodSelect`; `focus: FocusKey|null` dims non-focused series.
- **Title**: `pres.cardTitle` (static; NOT period-suffixed).

### 3.15 `PqAiSummaryCard` (card 25)
`harmonics-pq/HarmonicsPqTab.tsx`
- **Primitives**: `Card`/`CardHeader` → label (`pres.badgeLabel`, TYPOGRAPHY.aiLabel) + `AiSummary(density=pres.density)`. `ListBodySkeleton rows={4}`.
- **Payload → primitive**: `aiText = backendAiSummary ?? composeHpqAiText({pres, period, focus, stats, selectedPanel})` — backend paragraph REPLACES the local composition.
- **Closed vocab**: `pres` sentence vocab consumed inside `composeHpqAiText` (viewModel); `focus` FocusKey union.
- **State/interactions**: stateless.
- **Title**: `pres.cardTitle`.

### 3.16 `PqFeederTable` (card 26)
`harmonics-pq/HarmonicsPqTab.tsx`
- **Primitives**: `Card`/`CardHeader` → **`DataTable<PQPanelState>`** (same fill-height/sticky/select config as card 22); local `NumericCell` (Space Mono value + Inter unit suffix).
- **Payload → primitive**: rows = `period.panels`; column roster `pres.columns[].{id,header,align,fit,unit}` + `pres.columnOrder`; decimals `pres.decimals.{thd,pfLow,pfHigh}` + `pres.pfDecimalThreshold`; driver codes `shortDriver(p.driver, pres.driverCodeMap, pres.driverFallbackCode)`; label rewrite `pres.panelLabelReplacements`; layout + palette blocks as card 22.
- **Closed vocab**: `feederColumn()` switches on `FeederColumnId = 'panel'|'iThd'|'vThd'|'pf'|'iThdPk'|'driver'`; fixed accessors `p.truePf` (null → '—'), `p.iThd`, `p.vThd`, `p.iThdPk`, `p.driver`; unknown id → null cell.
- **State/interactions**: controlled `selectedPanelId` + `onPanelSelect` (row click).
- **Title**: `` `${pres.titlePrefix}${pres.titleConnector}${period.label}` ``.

### 3.17 `SignatureCard` (card 27)
`harmonics-pq/HarmonicsPqTab.tsx`
- **Primitives**: `Card`/`CardHeader` → **`ComparisonRadarChart`** (2 series: selected vs fleet) + local `SignatureRail`/`SignatureRailApi` (2-col dt/dd grids + driver footer). `CardBodySkeleton rail railRows={3}`.
- **Payload → primitive**: TWO modes.
  - API mode (`apiSignature` present): `pres.spokes` (labels, e.g. 'H5 (%)') + `apiSignature.selectedValues[]/fleetAvgValues[]` → the two radar series; rail picks ≤3 axes via `pres.rail.preferredAxes` with normalization (`axisKey` strips ' (…)'; prefix rule so 'K' matches 'K-FACTOR' not 'KVA'), fallback `pres.spokes.slice(0, rail.fallbackCount)`.
  - Mock mode: series values HARD-WIRED from panel fields — selected `[p.h3,p.h5,p.h7,p.iThd,p.vThd,p.kFactor]`, fleet = `avg()` of the same six across `period.panels`; rail rows `pres.rail.selectedRows/fleetRows[].{label, metricKey∈'iThd'|'vThd'|'kFactor', unit, decimals}`.
  - Common chrome: `pres.{title,selectedName,fleetName,gridTemplateColumns}`, `pres.palette.{selectedColor,fleetColor,textPrimary,textMuted,textLabel,dividerColor}`, `pres.style.{selectedStrokeWidth,fleetStrokeWidth,fleetFillOpacity}`, `pres.dividerStyle`; driver phrase `resolveDriverPhrase(selected, pres.rail.driverVocab)` (free-text `p.driver`-ish override wins), label `pres.rail.driverLabel`.
- **Closed vocab**: mock-mode spoke ORDER/fields fixed to the six `h3,h5,h7,iThd,vThd,kFactor`; rail `metricKey` union `'iThd'|'vThd'|'kFactor'`; `HpqDriverKey = 'H5'|'H7'|'V'|'PF'|'N'|'OK'`. API mode is roster-generic (values are positional arrays against `pres.spokes`).
- **State/interactions**: `selectedPanelId` picks the selected series (fallback `panels[0]`).
- **Title**: `pres.title`.

### 3.x Host `withSectionSplit` wrapper (`host/web/src/cmd/section-split.tsx`)
Applies to card 20 in BOTH tiers. Dispatch: `props.pres.sectionSplit === true` → replace the closed-accessor
card with a key-generic `EventTimelineChart` build (`value: p => p[key]` from `pres.stackSeries/stackOrder/
lineSeries/lineOrder`) or, for radar-shaped compare payloads, per-section series from `pres.sections
([{token,label,color}])` + `pres.spokeLabelReplacements`; title reuses `titlePrefix/titleConnector/period.label`.
No marker → original component byte-identical. This wrapper IS the existing proof-of-concept for the
generic-primitive dispatch this port is after.

---

## 4. Pres-vocabulary keys that could DISPATCH payload shapes to primitive families generically

Observed recurring pres/payload SHAPES → primitive family mapping (a generic renderer could switch on these
instead of card_id):

| Dispatch signal (payload/pres shape) | Primitive family | Cards exhibiting it |
|---|---|---|
| `pres.stackSeries + pres.stackOrder + pres.lineSeries + pres.lineOrder + points[]/periods[]` (+ `leftAxisLabel`, `rightAxis{label,unit}`, `dimOpacity`) | `EventTimelineChart` (stacked bars + overlay lines) | 20, 24 — and the section-split wrapper already renders this GENERICALLY with `p[key]` accessors |
| `pres.tiles + pres.tileOrder` (+ `key/label/swatch/color/payload/representsAll/unit/decimals`) with a `stats` record | `MetricTileGrid` | 18, 23 |
| `pres.segments + pres.segmentOrder` + `stats` counts | `SegmentBar` | 18, 23 |
| `pres.controls{presetOptions,resampleOptions,…}` + `filterSelection` | `EventStripControls` (filter row) | 18, 23 |
| `pres.columns + pres.columnOrder + period.panels` (+ `layout{headerHeight,rowHeight}`, `palette{rowHover/Selected*}`) | `DataTable` | 22, 26 — needs the per-column accessor made generic: `render: row => row[col.id]` + optional `unit/decimals/vocab` formatting instead of switch-on-id |
| `spokes[] {id,label,value}` or `pres.spokes + series[].values[]` (+ `pres.radar.*` / `pres.palette+style`) | `RadarChart` / `ComparisonRadarChart` | 21, 27 (27's API mode is already positional-generic) |
| `pres.cardTitle/aiLabel/badgeLabel/density` + one text field (`backendHeadline`/`ai_summary.text`) | `AiSummary` (in BodyCard/Card) | 19, 25, and AiSummary sub-blocks of 7, 13, 14–17 |
| `view.legend[] {id,color,label,(subRows)}` + `view.points[]` with `[seriesId]: number` index signature | grouped-bar / multi-line chart via `fieldOf(point, row.id)` + `ExpandableLegend` + `useInteractiveLegend` | 16, 17 — ALREADY roster-generic; the model for de-closing 20/24 |
| `view.segments + capacityValue(+capacityUsedValue) + markerPct` | `TickProgressBar` | 14/15 |
| `view.metrics[]/stats[] {id,label,value,unit,sub,(color)}` | `KpiStatStrip` | 14/15, 17 |
| `stats[] {label,value,unit,trend{dir,label}}` | `KpiMiniCard` grid | 11 (QuickStats) |
| `vm.sankey {nodes[layer,stageTitle,value], links}` + `vm.legend` + `vm.stageUnit` | `FlowSankey` + `SankeyLegend` | 13 |
| `vm.sources/consumers` hierarchical rows `{label,kwh,utilizationPct,color}` + section/total metas | rail list (RailRow family — candidates for a `DataTable`-like or list primitive) | 12 |
| `trend.series: number[]` (+ `lineColor`, `areaOpacity`, `bottomStats`) | sparkline (currently hand-drawn SVG — port target: a sparkline primitive) | 10 |
| `titlePrefix + titleConnector + period.label` | in-card title convention (BodyCard/CardHeader) | 20, 21, 22, 26 (+ section-split); static-title cards use `cardTitle`/`title`/`view.title`/`vm.*CardTitle` |
| `pres.sectionSplit: true` (+ `pres.sections`) | executor's existing generic-override marker | 20 today; the natural flag to widen |

**Port blockers (the closed vocabularies to neutralize):**
1. Timeline accessor records (`stackValueFor`/`lineValueFor`) — cards 20/24; fix = key-generic `p[key]` (section-split already does).
2. Table column `switch(col.id)` — cards 22/26; fix = accessor-by-id + declarative formatter (`unit/decimals/percent/vocab[key]`).
3. Tile `tileItem` key literals (`total/vDev/iImb/worstI/worstV`) — cards 18/23; fix = tile-level `valuePath`/`kind` in pres.
4. SignatureCard mock-mode fixed six-field spoke order — card 27; API mode (positional `values[]` vs `pres.spokes`) is the generic shape to standardize on.
5. Sankey↔rail node-id string conventions (`meter-*`/`incomer-*`) — cards 12/13; fix = explicit `nodeId` on rows.
6. RT dir/tone maps (`RT_DIR_PRESETS`, `RAIL_TONE_TO_DS`) — cards 9–11; already payload-overridable, only the KEY unions are closed.
7. Range/sampling preset unions (`EnergyTrendRangeOption` etc.) — cards 14–17; the picker rosters already ride the payload, only the value enums are closed.
