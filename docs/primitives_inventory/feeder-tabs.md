# Primitives inventory — `feeder-tabs` card family (cards 36–49)

Scope: `host/web/src/cmd/components/feeder-tabs.ts` (COMPONENTS barrel) + the FILL barrels that
shadow it, and the 12 distinct CMD_V2 page-card components they mount. CMD_V2 root =
`/home/rohith/CMD_V2/src` (the host `@cmd-v2` alias). Written for a primitives-only render port:
what each card actually mounts, which payload paths feed which primitive, and which vocabularies
are CLOSED (cannot be rebound by a payload).

---

## 1. COMPONENTS registry (`host/web/src/cmd/components/feeder-tabs.ts`)

"EQUIPMENT-DETAIL / FEEDER deep-tab family barrel (cards 36–49)". 14 card ids → 12 distinct components
(43/45 and 44/46 reuse one component each):

| card_id | Component | CMD_V2 source path (under `/home/rohith/CMD_V2/src/`) |
|---|---|---|
| 36 | `PowerEnergyPanel` | `pages/electrical/tabs/real-time-monitoring/PowerEnergyPanel.tsx` |
| 37 | `VoltageMonitorPanel` | `pages/electrical/tabs/real-time-monitoring/VoltageMonitorPanel.tsx` |
| 38 | `CurrentMonitorPanel` | `pages/electrical/tabs/real-time-monitoring/CurrentMonitorPanel.tsx` |
| 39 | `TodaysEnergyCard` | `components/charts/primitives/TodaysEnergyCard.tsx` |
| 40 | `PowerEnergyAnalysisChart` | `pages/electrical/tabs/energy-power/PowerEnergyAnalysisChart.tsx` |
| 41 | `InputOutputEnergyCard` | `pages/electrical/tabs/energy-power/InputOutputEnergyCard.tsx` |
| 42 | `LoadAnomaliesChart` | `components/charts/primitives/LoadAnomaliesChart.tsx` |
| 43 | `HealthSummaryPanel` | `pages/electrical/tabs/voltage-current/HealthSummaryPanel.tsx` |
| 44 | `HistoryPanel` | `pages/electrical/tabs/voltage-current/HistoryPanel.tsx` |
| 45 | `HealthSummaryPanel` (same as 43) | `pages/electrical/tabs/voltage-current/HealthSummaryPanel.tsx` |
| 46 | `HistoryPanel` (same as 44) | `pages/electrical/tabs/voltage-current/HistoryPanel.tsx` |
| 47 | `PowerQualityCard` | `pages/electrical/tabs/power-quality/PowerQualityCard.tsx` |
| 48 | `DistortionProfileChart` | `components/charts/primitives/DistortionProfileChart.tsx` |
| 49 | `LoadImpactChart` | `components/charts/primitives/LoadImpactChart.tsx` |

Note: 4 of the 12 (`TodaysEnergyCard`, `LoadAnomaliesChart`, `DistortionProfileChart`,
`LoadImpactChart`) already LIVE in `components/charts/primitives/` — they were "promoted" from
page folders and are themselves generic primitives with a payload-owned data contract.

## 2. FILL shadowing (FILL wins over COMPONENTS at render time)

Every one of the 14 ids is FILL-covered — the COMPONENTS barrel is fully shadowed for this family:

| card_ids | FILL barrel (`host/web/src/cmd/fill/`) | render-fn signature |
|---|---|---|
| 36, 37, 38 | `feeder-real-time-monitoring.tsx` → `feeder-real-time-monitoring/card-{36,37,38}.tsx` | `(payload)` — live-only, NO onDateChange |
| 39, 40, 41, 42 | `feeder-energy-power.tsx` → `feeder-energy-power/card-{39..42}.tsx` | `(payload, frame?, onDateChange?)`; card 41 ignores onDateChange (snapshot card) |
| 43 | **`panel-overview-voltage-current.tsx`** → `panel-overview-voltage-current/card-43.tsx` | `(payload)` — the equipment-detail Voltage Health Summary is registered in the PANEL-OVERVIEW barrel, not a feeder barrel |
| 44, 45, 46 | `feeder-voltage-current.tsx` → `feeder-voltage-current/card-{44,45,46}.tsx` | `(payload, frame?, onDateChange?)`; card 45 ignores onDateChange |
| 47, 48, 49 | `feeder-power-quality.tsx` → `feeder-power-quality/card-{47,48,49}.tsx` | `(payload, frame?, onDateChange?)`; card 47 has no date control |

Cross-family gotchas recorded in the barrels:
- Cards 40 & 41 are the SAME two equipment-detail cards the panel-overview/energy-power page lists;
  the registry is card_id-keyed GLOBALLY, so `feeder-energy-power.tsx` OWNS 40/41 and the
  panel-overview barrel no longer re-exports them (duplicate-registration guard).
- FRAMES ARE RETIRED everywhere: the ONLY data source is the Layer-2 completed `payload`
  (harvested Storybook story-args shape); the `frame` arg is always empty and ignored.
- ALWAYS-DRAW rule: no card ever returns null; unusable slices fall back to CMD_V2's OWN
  structured-empty view-model (`createUnavailableRealTimeMonitoringViewModel`, `emptyDistortion()`
  via `createPowerQualityViewModel({} as snapshot)`, `unavailableHistory/unavailableHealth` from
  `fill/shared/vc-empty`, `honestEmptyHealth`, `placeholderSnapshot`) + NaN-guards
  (`fill/shared/vc-sanitize`, `sanitizeSnapshot`).

Fill payload root per card (what Layer 2 must emit):

| card | payload shape (story args) |
|---|---|
| 36 | `{ data: PowerEnergyViewModel, freshness: RealTimeFreshnessViewModel }` |
| 37/38 | `{ data: PhaseMonitorViewModel, freshness }` |
| 39 | `{ variant, data: TodaysEnergyData }` |
| 40 | `{ variant, data: PowerEnergyAnalysisData }` |
| 41 | `{ variant, data: InputOutputEnergyData }` — fill forces the 5 numeric leaves finite (component `.toLocaleString()`s unguarded) |
| 42 | `{ variant, data: LoadAnomaliesData }` |
| 43 | `{ health: { data: HealthCardData, phaseVariant } }` |
| 44/46 | `{ variant, history: { data: HistoryPanelData } }` |
| 45 | `{ variant, health: { data: HealthCardData, phaseVariant } }` |
| 47 | `{ variant, snapshot: PowerQualitySnapshot }` |
| 48 | `{ variant, distortionProfile: ProfileChartData<'v-thd'\|'i-thd'\|'h5-h7'> }` |
| 49 | `{ variant, loadImpact: LoadImpactData<'pf-health'\|'pf-angle'\|'k-stress'> }` |

Date wiring (fill-owned, not in the CMD_V2 component):
- 39/40/42: `feeder-energy-power/date-wiring.ts` `periodToDateWindow(label)` — period LABEL string →
  `{range: today|yesterday|last-7-days|this-month, sampling: 2hour|day|week}`.
- 44/46: `feeder-voltage-current/date-wiring.ts` `withDateControl(data, onDateChange)` injects
  `data.sampling`/`data.onSamplingChange` ONTO the HistoryPanel payload (functions ride the payload).
- 48/49: `feeder-power-quality/date-window.ts` `samplingToDateWindow(SamplingSelection)` →
  host date_window (`custom` → `custom-range` + start/end); sampling chrome from
  `powerQualitySampling` (`SAMPLING`, `SAMPLING_RESOLUTION_OPTIONS`, `POWER_QUALITY_SAMPLING_PRESETS`).

---

## 3. Per-component inventory

### 3.1 `PowerEnergyPanel` (card 36) — real-time Power & Energy strip + rail

Props: `{ data: PowerEnergyViewModel, freshness: RealTimeFreshnessViewModel, availability? }`.

Primitives mounted (arrangement: `Card > CardHeader(title+LiveTag) > [PowerEnergyChart | PowerEnergyRail]`):
- `Card`, `CardHeader`, `LiveTag`, `CardBodySkeleton` (loading), `useInteractiveLegend`
- `PowerEnergyChart` (sibling file, itself composed of `ResponsiveSvg, ChartFrame, GridAxis,
  LinePath, ChartHoverCapture/Crosshair/Tooltip, ChartTooltipCard` from primitives)
- `PowerEnergyRail` (sibling file — `InteractiveLegendRow` ×4 + plain `RailMetricRow`s)

Payload → primitive mapping:
- `data.title` → header; `freshness.{label,tone,title}` → `LiveTag`.
- `data.dataSeries: [number[], number[]]` (normalized 0..1) + `data.rawSeries` (hover reals) +
  `data.sampleTimestamps` / `axisStartMs` / `axisEndMs` / `timeLabels` / `timeLabelTimestamps` →
  chart; `data.yLabels`, `xAxisLabel`, `yAxisLabel` → axis; `hoverSeries[{label,unit,color}]`,
  `hoverLabels`, `hoverValueDecimals`, `showHoverTooltip` → tooltip.
- Rail: `data.readings.{activePower,reactivePower,activeEnergy,reactiveEnergy}` are `FormattedMetric`
  `{label,displayValue,unit}` → 4 `InteractiveLegendRow`s; `data.railLabels.{projected,apparent,dkwDt,kvarTrend}`
  + `readings.{projectedDemand,apparentPower}.displayValue/unit`, `readings.activePowerDeltaPerMinute`,
  `` `${trend==='rising'?'↑':'↓'} ${readings.reactivePowerTrendLabel}` `` → metric rows.

CLOSED vocabulary (cannot rebind via payload):
- `POWER_ENERGY_KEYS = ['Active Power','Reactive Power','Active Energy','Reactive Energy']`
  (constants.ts) — the interactive-legend key union; opacities map to the FIXED record
  `{activeLine, reactiveLine, activeArea, reactiveArea}` = `opacityFor('Active Power')` etc.
- `readings` is a FIXED accessor record (`activePower/reactivePower/activeEnergy/reactiveEnergy/
  projectedDemand/apparentPower/activePowerDeltaPerMinute/reactivePowerTrend/reactivePowerTrendLabel`)
  — the rail hard-reads each key; extra/renamed series cannot appear.
- `dataSeries` is a fixed 2-tuple (exactly 2 plotted series); `reactivePowerTrend ∈ 'rising'|'falling'`
  drives the ↑/↓ glyph + color (chrome derivation).

Local state/interaction: `useInteractiveLegend` focus/dim per legend key (rail checkbox rows toggle
chart opacities). No date control (live-only). Title = `data.title` verbatim (no prefix/connector).

### 3.2 / 3.3 `VoltageMonitorPanel` (37) & `CurrentMonitorPanel` (38) — byte-identical twins

Props: `{ data: PhaseMonitorViewModel, freshness, availability? }`. Both are 48-line wrappers that
spread `{...data}` into the shared primitive **`PhaseMonitorPanel`**
(`components/charts/primitives/PhaseMonitorPanel.tsx`) + `liveLabel/liveTone/liveTitle` from freshness.

`PhaseMonitorPanel` primitives: `Card > CardHeader(title, action=LiveTag) > [PhaseMonitorChart | rail]`;
rail = `InteractiveLegendRow` per `legendItems[]` + plain label/value rows per `metrics[]`;
`useInteractiveLegend` keyed on `legendItems[].label`.

Payload → primitive mapping (`PhaseMonitorViewModel`):
- `series: {data:number[], color}[]` (index-aligned with `legendItems` — caller contract) → `PhaseMonitorChart`
- `yTicks: string[]`, `yAxisLabel`, `xAxisLabel`, `timeLabels`, `timeLabelTimestamps`,
  `sampleTimestamps`, `axisStartMs/axisEndMs` → axes (ts→x over `[axisStartMs,axisEndMs]`)
- `thresholds: {value,label}[]` → reference lines; `legendItems: {color,label,value?}[]` → rail legend
- `metrics: {label,value}[]` → rail metric rows; `showHover/hoverUnit/hoverValueDecimals/hoverLabels` → tooltip

CLOSED vocabulary: almost none — series roster, legend labels, thresholds, metrics are all
payload-driven arrays (the producer copies `PHASE_MONITOR_ROSTER` B/R/Y colors+labels onto the
payload). Chrome only: rail fixed at 209px, `axisKey` accepted-but-unused. This is the most
port-ready card of the family. Title = `data.title` verbatim.

### 3.4 `TodaysEnergyCard` (card 39) — progress/tile card (already a primitive)

Props: `{ data: TodaysEnergyCardData, onPeriodChange?, title? }`.

Primitives: `Card > CardHeader(title, action=[StatusBadge?, FilterPillSelect]) > headline row >
TickProgressBar > KpiStatStrip(3 cells) > AiSummary(insight, compact)`.

Payload → primitive mapping:
- Numbers: `activeEnergyKwh + reactiveEnergyKwh` (headline total unless `totalEnergyKwh` given),
  `energyTargetKwh` (headline `/target` + bar denominator), `subsidyLimitKw` →
  `subsidyMarkerPct ?? (subsidyLimitKw/energyTargetKwh)*100` marker, `secKwhPerUnit` → SEC cell.
- Bar: `toSegments()` builds `[{id:'active',weight:activeEnergyKwh,color:activeColor},
  {id:'reactive',...},{id:'remainder', weight:target-used, color:remainderColor}]` → `TickProgressBar`.
- Tiles: hard-coded 3 `KpiStatStrip` cells `id: 'active' | 'reactive' | 'sec'` with
  `label/value/unit/swatch` from `activeLabel/reactiveLabel/secLabel/energyUnit/secUnit/activeColor/reactiveColor`.
- `period` + `periodOptions: string[]` → `FilterPillSelect` (`options = periodOptions.map(p=>({value:p,label:p}))`).
- `insight?` → footer `AiSummary`; `staleBadge?` → `StatusBadge`.
- §B4 metadata all payload-owned, read PLAINLY (no `?? CONST`): `title, headlineUnit, subsidyLabel,
  subsidyUnit, noTargetFallback, periodAriaLabel, activeLabel, reactiveLabel, secLabel, energyUnit,
  secUnit, activeColor, reactiveColor, remainderColor`.

CLOSED vocabulary: the numeric accessor NAMES (`activeEnergyKwh`, `reactiveEnergyKwh`,
`energyTargetKwh`, `subsidyLimitKw`, `secKwhPerUnit`) and the fixed 3-cell KPI arrangement +
fixed segment ids `active/reactive/remainder`; `en-IN` `toLocaleString` formatting; NaN → `'—'` guard.

Interaction: `onPeriodChange(period)` from the pill (fill maps → `periodToDateWindow`). Title:
`title` prop wins else `data.title` (single string, no composition).

### 3.5 `PowerEnergyAnalysisChart` (card 40) — stacked bars + avg line, 2-view rail

Props: `{ data: PowerEnergyAnalysisData, onPeriodChange?, onResolutionChange?, onCustomRangeChange?,
availability?, historyLoading? }`.

Primitives: `Card > CardHeader(title, action=[StatusBadge?, SamplingPicker]) > grid[
ResponsiveSvg( PowerEnergySvg | DemandEnergySvg ) | aside rail( SegmentedControl view-toggle,
InteractiveLegendRow ×3 or DemandLegendRail, AiSummary(insight) ) ]`. Inner SVG uses
`ChartFrame, GridAxis, StackedBars(+buildDivergingSegments), LinePath, ReferenceLine,
ChartHoverCapture/Crosshair/Tooltip, ChartTooltipCard, sparseTickIndexes`.

Payload → primitive mapping:
- A/R view: `data.bars: {time, active, reactive}[]` → diverging stacked bars;
  `data.hourlyAverage: number[]` → overlay `LinePath` + white/color dot markers;
  `data.yMin/yMax` → domain; `data.yAxisTitle {label,unit,unitStyle}` → `composeMetricHeader` axis title;
  `data.ratedKw/contractedKw` + `ratedKwPlacement/contractedKwPlacement` + `ratedLabel/contractedLabel/refLineUnit`
  → `NameplateRefLines` (off-scale placement ⇒ omitted, data-first axis).
- Demand view: `data.demandBars: {time, value, band}[]`, `demandYMin/demandYMax`,
  `demandRatedKwPlacement/demandContractedKwPlacement`; bar fill resolved from
  `data.demandBandLegend[{band,label,threshold,color}]` (one source for rail + bars).
- Rail: `activeLegendLabel/Unit + data.activePowerAvgKw.toFixed(1)`,
  `reactiveLegendLabel/Unit + reactivePowerAvgKw` (value is kVAr; field name stale), `averageLegendLabel`
  (swatch="line"); colors `activeColor/reactiveColor/averageColor`. `data.insight` → `AiSummary`.

CLOSED vocabulary:
- `view ∈ 'active-reactive' | 'demand'` (union; `useState(data.view ?? 'active-reactive')` — payload
  only SEEDS the toggle); `SERIES_KEYS = ['active','reactive','line']`; `DEMAND_BAND_KEYS = ['low','moderate','high']`
  (`bars[].band` must be one of these).
- `EP_PERIOD_PRESETS` (today/yesterday/last-7-days/this-month/last-month/custom) and
  `EP_RESOLUTION_OPTIONS` (hourly/by-shift) are COMPONENT consts (backend-capability config pinned
  by presets.test) — `periodToPreset/presetToPeriod` keyword-map the payload's `period` string onto them.
- Fixed 3-row A/R legend reading `activePowerAvgKw`/`reactivePowerAvgKw` accessors.

Local state/interaction: view toggle (SegmentedControl), `useInteractiveLegend` ×2 (A/R keys +
demand bands — click dims bars), `sampling` local `SamplingSelection` state → emits
`onPeriodChange/onResolutionChange/onCustomRangeChange`, hover index per view. Title = `data.title`.

### 3.6 `InputOutputEnergyCard` (card 41) — dual headline + loss bar (static)

Props: `{ data: InputOutputEnergyData, availability? }`. NO interactions, no date control.

Primitives: `Card > CardHeader(title, dividerTone="strong") > 2-col headline grid >
TickProgressBar(segments+marker) > below-bar dual labels > KpiStatStrip(3 cells) > AiSummary(insight)`.
(`ListBodySkeleton` when loading.)

Payload → primitive mapping:
- `hvInputKw`, `lvOutputKw` → left/right big headlines (labels `hvInputLabel/lvOutputLabel`, unit `powerUnit`).
- Derived IN-CARD: `lossKw = max(0, hv-lv)`, `deliveredPct = lv/hv*100`, `lostPct`, `markerPct=deliveredPct`.
- Bar segments FIXED: `[{id:'delivered',color:deliveredColor,weight:lvOutputKw},{id:'loss',color:lossColor,weight:lossKw}]`.
- KPI cells FIXED ids `loss / expected-loss / efficiency` ← `lossKwh, expectedLossKwh, efficiencyPct`
  with `lossLabel/expectedLossLabel/efficiencyLabel`, units `energyUnit/percentUnit`.
- §B4 payload metadata: `title, hvInputLabel, lvOutputLabel, powerUnit, percentUnit, energyUnit,
  deliveredDescriptor, lostDescriptor, lossLabel, expectedLossLabel, efficiencyLabel,
  deliveredColor, lossColor, lostValueColor, descriptorColor`.

CLOSED vocabulary + hazard: numeric accessors `hvInputKw/lvOutputKw/lossKwh/expectedLossKwh/efficiencyPct`
are `.toLocaleString()`'d with NO finite guard — the fill (`inputOutputData`) MUST coerce them
finite (honest-blank → 0) or the card crashes. Fixed 2-segment + 3-cell arrangement. Title = `data.title`.

### 3.7 `LoadAnomaliesChart` (card 42) — anomaly line chart + event drill-in (already a primitive)

Props: `{ data: LoadAnomaliesData, onPeriodChange?, onResolutionChange?, onCustomRangeChange?, title? }`.

Primitives: `Card > CardHeader(title, action=SamplingPicker) > grid[ ResponsiveSvg(AnomaliesSvg) |
aside( SelectedEventPanel XOR DefaultLegendRail ) ]`. AnomaliesSvg: `ChartFrame, GridAxis`, expected
range = raw `<path>` polygon, smooth `<path>`s for expected(dashed)/actual lines, `ReferenceLine`
(Max threshold, edge-clamped), `PresentReference` floating tag, `EventDot` pills, `ChartHover*` +
`ChartTooltipCard`; framer-motion snapshot smoothing (`useSmoothedLoadAnomaliesData`, honors
reduced-motion). Rail: `InteractiveLegendRow`s + `AiSummary`.

Payload → primitive mapping:
- `actualLoad/expectedLoad: {time,value}[]`, `expectedRange: {time,min,max}[]` → the 3 plot layers;
  `yMin/yMax` domain; `maxThresholdPct` (+`maxThresholdPlacement`) → Max ref line;
  `presentValuePct` → right-anchored Present tag.
- `anomalies: LoadAnomalyEvent[]` → `EventDot`s; fields `time,value,type('surge'|'dip'),label,title,
  occurredAtTime,occurredAtDate,beforePct,eventPct,afterPct,peakLoadPct,expectedPct,deviationPct,
  durationMs,detail?` feed the click-to-open `SelectedEventPanel` (before/event/after cells +
  metric rows + `AiSummary(detail)`).
- Rail default: `data.colors.surge + labels.legendSurgeLabel + String(surgeEvents)`, dip likewise,
  `loadFactorPct + labels.loadFactorLabel + labels.pctUnit`, then actual/expected/range legend rows;
  `data.insight` → `AiSummary`.

CLOSED vocabulary:
- `data.labels` FIXED 28-key record (`title, yAxisUnit, pctUnit, durationUnit, maxLabel, presentLabel,
  belowLabel, aboveLabel, presentAriaPrefix, loadFactorLabel, legendSurgeLabel, legendDipLabel,
  legendActualLabel, legendExpectedLabel, legendRangeLabel, surgeTypeLabel, dipTypeLabel, beforeLabel,
  eventStatLabel, afterLabel, peakLoadLabel, expectedLabel, deviationLabel, durationLabel,
  eventFallbackText, closeAriaLabel, tooltipSurgeLabel, tooltipDipLabel`) — words morph, KEYS don't.
- `data.colors` FIXED 6-key record `{actual, expected, rangeFill, maxThreshold, surge, dip}`.
- `ANOMALY_LEGEND_KEYS` = 5 literal legend keys (`'Surge events'…'Expected Range'`) — the focus/dim
  identity union is hard-coded English regardless of the label words shown.
- `type ∈ 'surge'|'dip'`; `LA_PERIOD_PRESETS`/`LA_RESOLUTION_OPTIONS` component consts (same roster as 3.5).
- Chrome: pill backgrounds `destructive50/teal50`, dip-text `teal500`.

Local state/interaction: `selectedEventKey` (EventDot click swaps rail to event detail; close resets),
legend focus, local `SamplingSelection` → `onPeriodChange/onResolutionChange/onCustomRangeChange`,
bucket-hover. Title: `title` prop ?? `data.labels.title`.

### 3.8 `HealthSummaryPanel` (cards 43 & 45) — health snapshot (voltage=43, current=45)

Props: `{ data: HealthCardData, phaseVariant?: 'rows'|'bars', availability? }`.

Primitives: `Card > raw <header>(title + StatusBadge(staleBadge) + StatusPill(status)) >
[ HealthSummary headline + DeviationBand ] > MetricStrip(KpiStatStrip) >
PhaseRows(PhaseValueRows | PhaseBarRows) > Insight <p>`. (`CardBodySkeleton` loading.)

Payload → primitive mapping (`voltage-current/types.ts` `HealthCardData`):
- `title`; `status {label, tone, statusKey?}` + `statusVocab?[statusKey]` → pill WORD (vocab-resolved
  at leaf, fallback `status.label`); `staleBadge?`.
- `summary? {value, unit, label, caption?, nominal?, nominalUnit?, nominalLabel?, deviation?,
  deviationUnit?, sideLabel?, sideValue?, sideUnit?}` → headline; caption composed
  `` `${label} · ${nominalLabel ?? PRESENTATION_LABELS.nominal} ${nominal} ${nominalUnit}` ``.
- `band? {markerPct, labels: (string|MetricText)[]}` → `DeviationBand` marker + tick labels.
- `metrics: {label,value,unit?,note?,tone?}[]` → `KpiStatStrip` cells (warning tone → `warning600`).
- `phases: PhaseRow[]` (`label,color,widthPct,markerPct,value,unit?,deltaText?/delta,deltaTone`) →
  `PhaseValueRows` (variant 'rows') or local `PhaseBarRows` (variant 'bars': label · balance bar +
  nominal marker · value · tinted delta).
- `insight` (+ `insightVocab?[insightKey]` word resolution) → footer paragraph.

CLOSED vocabulary:
- `STATUS_PILL_BY_TONE: Record<'normal'|'warning', {tone,leading,glyph:'▲'}>` — tone set is closed
  (card-43 fill's honest-empty `tone:'neutral' as any` falls outside it → `statusPill` undefined → no pill).
- `DELTA_TONE: Record<'good'|'bad'|'neutral', color>`; `phaseVariant ∈ 'rows'|'bars'` (a PROP, not payload —
  fill reads it from `payload.health.phaseVariant`).
- `DeviationBand` segment geometry hard-coded: ¼ danger / ½ normal / ¼ danger fills with
  `voltageHealthBandDanger/Normal` colors — only `markerPct` + tick `labels` are payload.
- Lots of fixed typography/color chrome consts (no hex morphing).

Local state/interaction: NONE (pure snapshot; no date control — that's why cards 43/45 take no
onDateChange). Title = `data.title` verbatim.

### 3.9 `HistoryPanel` (cards 44 & 46) — V/I history line chart (voltage=44, current=46)

Props: `{ data: HistoryPanelData, availability?, cardLoading? }`.

Primitives: `Card > HistoryHeader(title + optional SamplingPicker) > [ col( HistoryStats=KpiStatStrip,
HistoryChart=ResponsiveSvg>ChartFrame ) | HistoryRail(InteractiveLegendRow list + Insight) ]`.
Chart internals: `HorizontalBand` (expected range), `GridAxis`, `ReferenceLine` ×2 (max/min, tone
"threshold", off-scale → dropped), `LinePath` per series (null values break the line — gap buckets),
`EventDot` per event, `ChartHover*` + `ChartTooltipCard` (opt-in).

Payload → primitive mapping (`HistoryPanelData`):
- `stats: {label,value,unit?,note?,noteKey?}[]` + `noteVocab?` → `KpiStatStrip` (note word vocab-resolved).
- `series: {label, color, values:(number|null)[]}[]` → `LinePath`s; `minY/maxY/yTicks/yTickDecimals/
  yAxisLabel/xLabels/xLabelIndexes` → axes; `expectedMin/expectedMax/showExpectedRange` → band;
  `maxLine/minLine {value, label:string|MetricText}` → threshold refs; `events: {index, seriesLabel,
  color}[]` → dots (swell/sag classified vs `expectedMax`).
- `legend: {label,color,shape?,swatch?,value?}[]` → rail rows (focus keys = `legend[].label`);
  `insight` → rail text; `hoverLabels/hoverUnit/showHoverTooltip` → tooltip.
- Sampling control rides the PAYLOAD: `data.sampling`, `data.onSamplingChange` (a FUNCTION — the fill's
  `withDateControl` injects it; JSON payloads can't carry it), `samplingPresets, showSamplingCalendar,
  showSamplingFooterSummary, samplingApplyLabel/CancelLabel/DialogAria`. Header picker renders only
  when BOTH `sampling` and `onSamplingChange` present.

CLOSED vocabulary (fallback literals — payload CAN override):
- `expectedRangeKey ?? 'Expected Range'` (band↔legend focus identity), `eventTypeKeys ?? {swell:'Swell
  events', sag:'Sag events'}`, legend swatch derivation (`shape==='dot'` / label`==='Expected Range'`).
- Band fill `COLORS.expected` from the tab's `constants.ts` — the expected-range COLOR is chrome, NOT payload.
- Axis chrome AXIS_STYLE (plex/sky600/cream200).

Local state/interaction: legend focus (`useInteractiveLegend` on `legend[].label`), hover index;
date control via payload-injected `onSamplingChange`. Title = `data.title` verbatim.

### 3.10 `PowerQualityCard` (card 47) — PQ summary rail card (no chart SVG)

Props: `{ snapshot: PowerQualitySnapshot, className? }`. Pure function of ONE payload; NO local state,
NO interactions, no date control.

Primitives: `Card > header(pres.title + StatusPill(ieeeBadge)) > KpiStatStrip(3: compliance/trend/
severity) > PqSectionDivider + SpectrumRow(iThd) + SpectrumRow(vThd) + SpectrumXAxis >
PqSectionDivider + SpectrumRow(h5) + SpectrumRow(h7) + SpectrumXAxis > PqSectionDivider +
KpiStatStrip(2: flicker-pst/crest-factor) > PqSectionDivider + KeyValueRowsCard(4 rows)`.
`SpectrumBar` (width 256, threshold marker) inside each SpectrumRow. (`CardBodySkeleton` loading.)

Payload → primitive mapping — everything reads `snapshot.presentation.*` (`pres`):
- Strip 1 FIXED ids `compliance/trend/severity`: value = `ieeeState==='fail' ? cs.complianceWords.fail
  : 'pass' ? cs.complianceWords.pass : cs.placeholder`; `trendLabel` + sub composed from
  `trendPctPerHour.toFixed(cs.trendDecimals)` + `UNITS.percentPerHour`; `severityLabel/severityAction`,
  high-severity tint when `severityLabel === cs.severityHighWord` (string-equality dispatch!).
- Spectrum: FIXED 4 readings `snapshot.{iThd,vThd,h5,h7}: {valuePct, limitPct, scaleMaxPct}` with
  pres rows `pres.spectrum.{iThd,vThd,h5,h7}: {primary, sub, valueDecimals}` and axis
  `pres.spectrum.axis {label, scaleMax, tickFractions, tickDecimals}`; limit fallback `PQ_LIMITS.*`;
  over-limit → `palette.spectrumOverLimit`.
- VQ strip FIXED cells `flickerPst {value, peakToday, limit, tone, statusBadge}` /
  `crestFactor {value, ideal, tone, statusBadge}`; tones via `toneToColor/toneToBadge` + `pres.palette`.
- `KeyValueRowsCard` FIXED 4 rows ← `likelySource / filterState / capacitorBank / nextPriority`
  (+`nextPriorityTone ∈ 'critical'|'watch'`), labels from `pres.sourceMitigation.*`.

CLOSED vocabulary: the accessor record is the widest of the family — `iThd/vThd/h5/h7`,
`flickerPst/crestFactor`, the 4 source-mitigation fields, `ieeeState ∈ 'pass'|'fail'|null`,
`PqTone ∈ 'critical'|'watch'|'ok'`; leaf-composed `UNITS.percent` / `UNITS.percentPerHour` registry
tokens; SpectrumBar 256px geometry. All WORDS/decimals/colours morph via `pres`, the SHAPE doesn't.
Title = `pres.title`.

### 3.11 `DistortionProfileChart` (card 48) — generic multi-view %-line chart (already a primitive)

Props: `{ data: ProfileChartData<TKey>, className?, onPeriodChange?, sampling?, onSamplingChange?,
samplingPresets?, samplingResolutionOptions?, samplingShowCalendar? }`.

Primitives: `Card > CardHeader(title, action=SamplingPicker) > grid[ ResponsiveSvg(ProfileChartSvg)
| aside( SegmentedControl(viewOptions), averageStat row, InteractiveLegendRow per series ) ]`.
SVG: `ChartFrame, GridAxis, ReferenceLine (maxLine/minLine tone 'threshold'), LinePath per series
(dashed via style), ChartHover* + ChartTooltipCard (opt-in)`.

Payload → primitive mapping (`ProfileChartData`):
- `views: Record<TKey, ProfileViewSlice>` + `view` (seed) + `viewOptions?` (tabs; inferred from keys
  when absent). Per slice: `series: {id?, label, color, values, style?, value?}[]`,
  `yAxisLabel/yMin/yMax/yTicks`, `maxLine?/minLine? {value,label}`, `averageStat? {label,value}`,
  `hoverUnit?/hoverDecimals?`. Shared `xLabels/xLabelIndexes`, `showHoverTooltip?`, `hoverLabels?`.

CLOSED vocabulary: essentially NONE in the primitive (generic by design — "does NOT bake any domain
naming"). Feeder payload pins `TKey = 'v-thd'|'i-thd'|'h5-h7'` via `power-quality/types.ts`.
Defaults: title `?? 'Distortion & Harmonic Profile'`, sampling default `{today, 2hour}`.
Legend focus keys = `series[].label`.

Local state/interaction: `view` (SegmentedControl, seeded from `data.view` — NOT controlled),
`localSampling` (fill passes controlled `sampling` + `onSamplingChange` → date_window), legend focus,
hover. Title = `data.title ?? default`.

### 3.12 `LoadImpactChart` (card 49) — generic multi-view line chart w/ KPI-grid or stat-list rail

Props: `{ data: LoadImpactData<TKey>, className?, sampling?, onSamplingChange?, samplingPresets?,
samplingResolutionOptions?, samplingShowCalendar? }`.

Primitives: `Card > CardHeader(title, action=SamplingPicker) > grid[ ResponsiveSvg(LoadImpactChartSvg)
| aside( SegmentedControl(viewOptions), KpiGrid XOR StatList, insight banner ✦ ) ]`.
SVG: `ChartFrame, GridAxis, ReferenceLine per watchLine (tone 'watch'|'threshold', dimmable),
LinePath per series, ChartHover* (opt-in)`.

Payload → primitive mapping (`LoadImpactData`):
- `views: Record<TKey, LoadImpactViewSlice>` + `view` + `viewOptions?`; per slice:
  `yAxisLabel/yMin/yMax/yTicks`, per-view `xLabels/xLabelIndexes`, `series[]`,
  `watchLines: {value,label,tone?,color?}[]`, **`railKind: 'kpi-grid' | 'stat-list'`** →
  `kpis: {label,value,sub?,color?}[]` (2×2 grid) OR `stats: {label,value,sub?,color?,swatch?{color,style}}[]`
  (swatch rows become `InteractiveLegendRow`), `compactMargin?`, `hoverUnit?/hoverDecimals?`.
- `insight?` → banner; `showHoverTooltip?/hoverLabels?`.
- Legend focus keys: `stats.filter(swatch).map(label)` else `series[].label`.

CLOSED vocabulary: `railKind` 2-value union is the only shape switch; PF-axis tick formatting
heuristic (`fractional && max<=1.5 → toFixed(2)`) is chrome. Feeder payload pins
`TKey = 'pf-health'|'pf-angle'|'k-stress'`. Default title `?? 'Load Impact & Transformer Stress'`.

Local state/interaction: view toggle (seeded from `data.view`), sampling (controlled by fill),
legend focus, hover. Title = `data.title ?? default`.

---

## 4. Title construction — whole family

**No `titlePrefix` / `titleConnector` / `period.label` composition exists anywhere in this family**
(grep over `pages/electrical/tabs/` + `components/charts/primitives/` = 0 hits). Every card's title
is ONE payload string rendered verbatim, with these variations:

| cards | title source | header extras |
|---|---|---|
| 36 | `data.title` | inline `LiveTag(freshness.label/tone/title)` |
| 37/38 | `data.title` (via PhaseMonitorPanel `title`) | `LiveTag` action |
| 39 | `title` prop ?? `data.title` | `StatusBadge(staleBadge)` + `FilterPillSelect(period)` |
| 40 | `data.title` | `StatusBadge(staleBadge)` + `SamplingPicker` |
| 41 | `data.title` | none (dividerTone="strong") |
| 42 | `title` prop ?? `data.labels.title` | `SamplingPicker` |
| 43/45 | `data.title` (raw `<header>`) | `StatusBadge(staleBadge)` + `StatusPill(statusVocab[statusKey] ?? status.label)` |
| 44/46 | `data.title` (raw `<header>`) | `SamplingPicker` only if payload carries `sampling`+`onSamplingChange` |
| 47 | `snapshot.presentation.title` | `StatusPill(ieeeBadge)` |
| 48 | `data.title ?? 'Distortion & Harmonic Profile'` | `SamplingPicker` |
| 49 | `data.title ?? 'Load Impact & Transformer Stress'` | `SamplingPicker` |

Period/date words never enter the title — the period lives in the header CONTROL
(`FilterPillSelect` value / `SamplingPicker` selection), driven by `data.period` + `data.periodOptions`
(39/40/42/48) or `data.sampling` (44/46/48/49 controlled).

## 5. Pres-vocabulary keys that could DISPATCH payload → primitive family generically

For a primitives-only port, the following payload shapes are discriminating enough to route a card
to a generic renderer without knowing its card_id (the ✅ ones already ARE the generic primitive):

| dispatch signature (keys present in payload slice) | primitive family | feeder cards |
|---|---|---|
| `views:Record<k,{series[],yTicks,xLabels}> + view (+viewOptions)` and per-slice `averageStat?/maxLine?` | multi-view line chart → **DistortionProfileChart** ✅ generic today | 48 |
| same + per-slice `railKind:'kpi-grid'\|'stat-list'` (+`kpis`/`stats`, `watchLines`) | multi-view line + KPI/stat rail → **LoadImpactChart** ✅ generic today | 49 |
| `series[{label,color,values}] + legend[] + stats[] + events[] + expectedMin/Max + maxLine/minLine` | history line chart w/ band+events → **HistoryPanel** (near-generic; needs `expectedRangeKey`/`eventTypeKeys` + band color lifted to payload) | 44, 46 |
| `series[{data,color}] + legendItems[] + metrics[] + thresholds[] + sampleTimestamps/axisStartMs/axisEndMs` | live 3-phase strip → **PhaseMonitorPanel** ✅ generic today | 37, 38 |
| `dataSeries:[[],[]] + rawSeries + readings{...} + railLabels{...}` | live dual line/area + fixed rail → PowerEnergyPanel (NOT generic: fixed `readings` accessor record; port = generalize rail to `readings[]` list) | 36 |
| `bars[{time,active,reactive}] + hourlyAverage[] + demandBars[{time,value,band}] + demandBandLegend[]` | stacked-bars+avg-line 2-view → PowerEnergyAnalysisChart (semi-generic; view/series keys closed) | 40 |
| `actualLoad/expectedLoad/expectedRange + anomalies[] + labels{} + colors{}` | anomaly line chart + event drill → LoadAnomaliesChart (labels/colors records fixed-key) | 42 |
| `activeEnergyKwh + energyTargetKwh + secKwhPerUnit + activeColor/reactiveColor` (or generically: `segments/weights + marker + 3 KPI cells + period/periodOptions`) | progress-bar tile card → TodaysEnergyCard (port = `tiles[] + segments[]`) | 39 |
| `hvInputKw + lvOutputKw + lossKwh/expectedLossKwh/efficiencyPct` (generically: 2 headline metrics + 2-segment bar + KPI cells) | dual-headline loss card → InputOutputEnergyCard | 41 |
| `summary + band + metrics[] + phases[] + status{tone}` | health snapshot → HealthSummaryPanel (metrics/phases already list-shaped; band+status tones closed) | 43, 45 |
| `presentation{complianceStrip,spectrum,voltageQuality,sourceMitigation,palette} + iThd/vThd/h5/h7 + flickerPst/crestFactor` | KPI-strips + spectrum-rows + KV-rows stack → PowerQualityCard (port = generic `sections[]` of `{kind:'kpi-strip'\|'spectrum-row'\|'kv-rows'}`) | 47 |

Generic pres-key candidates distilled (what a closed-vocab-free CMD_V2 payload could dispatch on):
- `pres.views` + `pres.view` → tabbed multi-view chart (48/49 pattern; 40's A/R-vs-demand collapses onto it).
- `pres.series` (list of `{label,color,values}`) → LinePath family; `+pres.bars` (`{time,…}` stacks) → StackedBars family.
- `pres.legend` / `pres.legendItems` → InteractiveLegendRow rail; `pres.metrics`/`pres.stats`/`pres.kpis`
  → KpiStatStrip / KpiGrid; `pres.tiles`+`tileOrder` equivalent here is the KPI cells array.
- `pres.segments` + `pres.marker` → TickProgressBar (39/41).
- `pres.events` / `pres.anomalies` → EventDot overlays (+ drill-in when the event objects carry the
  before/event/after stat fields).
- `pres.expectedMin/expectedMax` or `pres.expectedRange` → HorizontalBand / area band.
- `pres.maxLine/minLine/watchLines/thresholds` + `ratedKw/contractedKw`+`*Placement` → ReferenceLine family.
- `pres.insight` → AiSummary footer; `pres.staleBadge`/`pres.status`/`pres.ieeeBadge` → StatusBadge/StatusPill;
  `pres.freshness` → LiveTag.
- `pres.period/periodOptions` vs `pres.sampling/samplingPresets` → FilterPillSelect vs SamplingPicker
  header control (44/46 prove the picker can be entirely payload-declared — minus the callback).

Port hazards to carry:
1) Fixed accessor RECORDS (36 `readings.*`, 47 `snapshot.iThd/...`, 42 `labels/colors`, 41/39 numeric
   fields) — closed-vocab CMD_V2 accessors crash/blank on variant keys (known V48 gotcha).
2) Interaction identity keys are LITERAL unions in 36 (`POWER_ENERGY_KEYS`) and 42
   (`ANOMALY_LEGEND_KEYS`) — label morphs don't move the focus keys; 44/46 already fixed this via
   payload identity keys (`expectedRangeKey`, `eventTypeKeys`) — the pattern to replicate.
3) `data.view` / `data.period` only SEED `useState` — payload updates won't re-drive the toggle/picker
   (uncontrolled). 48/49 accept a controlled `sampling` prop; 40/42 don't.
4) `HistoryPanelData.onSamplingChange` is a function ON the payload — JSON-hostile; the fill injects
   it (`withDateControl`). A generic port needs the same injection seam.
5) `en-IN` locale formatting + unguarded `.toLocaleString()` in 41 (fill must pre-coerce finite).
