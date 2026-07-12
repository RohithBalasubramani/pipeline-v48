# DG card family (cards 60–73) — primitives-only render-port inventory

Sources read 2026-07-12:
- Host barrel: `host/web/src/cmd/components/dg.ts`
- Fill barrels: `host/web/src/cmd/fill/{dg-engine-cooling,dg-fuel-efficiency,dg-operations-runtime,diesel-generator-voltage-current}.tsx` (+ per-card folders)
- Dispatcher: `host/web/src/cmd/registry/render-cmd.tsx` (tier order **SPECIAL → FILL → COMPONENTS → COMPOSE → HonestBlank**; FILL SHADOWS COMPONENTS — line 59–65)
- CMD_V2 components under `/home/rohith/CMD_V2/src` (the `@cmd-v2` alias root)

---

## 1. card_id → renderer map

### 1a. `components/dg.ts` COMPONENTS registry (direct payload spread via `unwrap()`)

| card_id | import | CMD_V2 source path |
|---|---|---|
| 66 | `HealthSummaryPanel` (as CmpHS) | `@cmd-v2/pages/electrical/tabs/voltage-current/HealthSummaryPanel` |
| 67 | `HistoryPanel` (as CmpHP) | `@cmd-v2/pages/electrical/tabs/voltage-current/HistoryPanel` |
| 68 | `HealthSummaryPanel` (CmpHS again) | same as 66 |
| 69 | `HistoryPanel` (CmpHP again) | same as 67 |
| 70 | `LiveOpsCard` (Cmp70) | `@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/LiveOpsCard` |
| 72 | `EnergyReliabilityCard` (Cmp72) | `@cmd-v2/pages/assets/diesel-generator/tabs/operations-runtime/EnergyReliabilityCard` |

Ids 60/61/62/63/64/65/71/73 are deliberately NOT in dg.ts (need a module-default view-model the payload lacks, or carry no Storybook payload → FILL; 60 is a viewer envelope → SPECIAL).

### 1b. FILL registries overlapping this family (FILL wins over COMPONENTS at render time)

| card_id | title | fill barrel (CARDS registry) | per-card file | mounts |
|---|---|---|---|---|
| 61 | Thermal Timeline | `fill/dg-engine-cooling.tsx` | `dg-engine-cooling/card-61.tsx` | `Panel` (EngineHistoryCharts) in `EngineHoverProvider` |
| 62 | Pressure·Speed·Load | `fill/dg-engine-cooling.tsx` | `dg-engine-cooling/card-62.tsx` | `Panel` (mech chart) |
| 63 | Fuel Tank Anatomy (3D) | `fill/dg-fuel-efficiency.tsx` | `dg-fuel-efficiency/card-63.tsx` | `FuelTankAnatomy` |
| 64 | All Runs / Fuel Log | `fill/dg-fuel-efficiency.tsx` | `dg-fuel-efficiency/card-64.tsx` | `RunsList` (FuelHistoryCharts) |
| 65 | Fuel & Tank Composite | `fill/dg-fuel-efficiency.tsx` | `dg-fuel-efficiency/card-65.tsx` | `FuelCompositeCard` in `FuelHoverProvider` |
| 66 | Voltage Live Health | `fill/diesel-generator-voltage-current.tsx` | `card-66.tsx` | `HealthSummaryPanel` (**shadows** dg.ts entry) |
| 67 | Voltage History | same barrel | `card-67.tsx` | `HistoryPanel` (**shadows**) |
| 68 | Current Live Health | same barrel | `card-68.tsx` | `HealthSummaryPanel` (**shadows**) |
| 69 | Current History | same barrel | `card-69.tsx` | `HistoryPanel` (**shadows**) |
| 71 | Runtime & Duty | `fill/dg-operations-runtime.tsx` | `dg-operations-runtime/card-71.tsx` | `RuntimeDutyPanel` |
| 73 | Power Energy Analysis | `fill/dg-operations-runtime.tsx` | `dg-operations-runtime/card-73.tsx` | `PowerEnergyAnalysisPanel` (**already a shared primitive**) |

- **66–69 are registered in BOTH tiers**: renderCmd reaches FILL first, so the fill versions serve (they add `sanitizeHealth/sanitizeHistory` from `fill/shared/vc-sanitize`, structured-empty fallbacks from `fill/shared/vc-empty`, and SamplingPicker wiring). The dg.ts entries are dead-at-runtime backstops. (Barrel comments claiming "COMPONENTS before FILL" are stale — the tier flip is documented in render-cmd.tsx lines 59–62.)
- **70/72 render via COMPONENTS only** (their FILL entries were deleted as dead duplicates). Payload is the harvested story arg `{variant, view: LiveOpsView|EnergyReliabilityView}`; `registry/unwrap.ts` opens the single-key box and aliases the inner object to `data`/`vm`/`view`, so `<LiveOpsCard view={...}/>` receives its prop.
- **60 (Engine 3D Callout Viewer) → SPECIAL[60]** (`cmd/special.tsx:113`, `Asset3dEnvelope`): asset_3d viewer ENVELOPE (bound GLB → CentralAssetViewer, unbound → honest ComingSoon3D). Not a CMD_V2 page card; excluded from the per-component inventory below.

---

## 2. Per-component inventory

### 2.1 HealthSummaryPanel — cards 66 (voltage) / 68 (current)
`/home/rohith/CMD_V2/src/pages/electrical/tabs/voltage-current/HealthSummaryPanel.tsx` (425 ln)

**Primitives mounted** (all from `components/charts/primitives`): `Card` (h-full shell) → header (`h3` title + optional `StatusBadge` staleBadge + `StatusPill`) → body column: `HealthSummary` (big value+unit local JSX) + `DeviationBand` (local band: absolute-positioned marker over a fixed cream 25/50/25 track) → `MetricStrip` = **`KpiStatStrip`** → `PhaseRows` = **`PhaseValueRows`** (`variant='rows'`) OR local `PhaseBarRows` (`variant='bars'` — the DG default) → `Insight` (styled `<p>`). Loading branch: `CardBodySkeleton kpiCells={3}`.

**payload → primitive mapping** (props = `{ data: HealthCardData, phaseVariant?, availability? }`; fill reads `payload.data`):
- `data.title` → header `h3`.
- `data.status.{label,tone,statusKey}` + `data.statusVocab` → `StatusPill` (word = `statusVocab[statusKey] ?? label`).
- `data.staleBadge.{label,tone}` → `StatusBadge`.
- `data.summary.{value,unit,label,caption,nominal,nominalUnit,nominalLabel,sideLabel,sideValue,sideUnit}` → hero value block; caption = `caption ?? "{label} · {nominalLabel ?? PRESENTATION_LABELS.nominal} {nominal nominalUnit}"`.
- `data.band.markerPct` → marker `left: clamp(16px, {pct}%, …)`; `data.band.labels[]` (string | MetricText) → tick row (`composeMetricText`); `data.summary.deviation/deviationUnit` → marker label.
- `data.metrics[] {label,value,unit,note,tone}` → `KpiStatStrip` cells (`sub: note`; `tone==='warning'` → warning600 value/unit color).
- `data.phases[] PhaseRow {label,color,widthPct,markerPct,value,unit,deltaText|delta,deltaTone}` → bars variant: label / cream track with `width:{clampPct(widthPct)}%` colored fill + nominal tick at `markerPct` / `composeValueUnit(value,unit)` / delta text colored by `DELTA_TONE[deltaTone]`. Rows variant discards widthPct/markerPct/delta (only label/color/value+unit).
- `data.insight` (+ `insightKey`/`insightVocab` word-resolution) → bottom `Insight` paragraph.

**Closed vocabularies**:
- `STATUS_PILL_BY_TONE: Record<'normal'|'warning',…>` — `status.tone` outside this union → pill silently hidden; the pill glyph/variant is derived, NOT payload-bindable.
- `DELTA_TONE: Record<'good'|'bad'|'neutral',string>` — `phase.deltaTone` is a fixed key union.
- `phaseVariant` union `'rows'|'bars'` (fill hard-codes `'bars'` via `healthPhaseVariant(payload)` default, honours a `payload.phaseVariant` override).
- `availability` union `'ready'|'partial'|'loading'|'unavailable'` (only `'loading'` branches).
- DeviationBand track proportions (25%/50%/25% danger/normal/danger) + colors are frozen chrome — payload only moves the marker.
- Fallback label token `PRESENTATION_LABELS.nominal`.

**State/interactions**: none — pure snapshot card. No date control (fill passes no onDateChange).

**Title**: single payload string `data.title` (e.g. "Voltage — Live Health"). No prefix/connector/period machinery.

**Fill guard-rails** (card-66/68 + `shared/vc-sanitize`): usability probe `Array.isArray(data.metrics) && Array.isArray(data.phases)` else `unavailableHealth('voltage'|'current')` structured-empty; `sanitizeHealth` drops a labels-less band and finitizes bar pcts.

---

### 2.2 HistoryPanel — cards 67 (voltage) / 69 (current)
`/home/rohith/CMD_V2/src/pages/electrical/tabs/voltage-current/HistoryPanel.tsx` (436 ln)

**Primitives mounted**: `Card` → `HistoryHeader` (title + optional **`SamplingPicker`**) → body row: LEFT column `HistoryStats` = **`KpiStatStrip`** + `HistoryChart` = **`ResponsiveSvg`** → **`ChartFrame`** → [**`HorizontalBand`** (expected range), **`GridAxis`**, **`ReferenceLine`** ×2 (max/min, dashed, THRESHOLD tokens), **`LinePath`** per series (smooth, gap-breaking on null), **`EventDot`** per event, opt-in **`ChartHoverCrosshair`/`ChartHoverCapture`/`ChartHoverTooltip`/`ChartTooltipCard`**]; RIGHT rail `HistoryRail` = **`InteractiveLegendRow`** list + `Insight` paragraph. Loading: `CardBodySkeleton kpiCells={3} rail railRows={4}`.

**payload → primitive mapping** (props `{ data: HistoryPanelData }`; fill reads `payload.data`):
- `data.title` → header.
- `data.stats[] {label,value,unit,note,noteKey}` + `data.noteVocab` → KpiStatStrip (`sub = noteVocab[noteKey] ?? note`).
- `data.series[] {label,color,values:(number|null)[]}` → one `LinePath` each; x = index scale over `series[0].values.length`, y = `(v-minY)/(maxY-minY)`.
- `data.minY,maxY,yTicks[],yTickDecimals,yAxisLabel,xLabels[],xLabelIndexes[]` → `GridAxis` ticks/labels.
- `data.expectedMin,expectedMax,showExpectedRange,expectedRangeKey` → `HorizontalBand` (opacity from legend focus of `expectedRangeKey ?? 'Expected Range'`).
- `data.maxLine/minLine {value,label:string|MetricText}` → dashed `ReferenceLine`s (off-scale lines dropped silently).
- `data.events[] {index,seriesLabel,color}` → `EventDot` at (`index`, series value); dot opacity ties to legend focus of series AND event-type key.
- `data.legend[] {label,color,value,shape,swatch}` → `InteractiveLegendRow` rail; `data.insight` → rail footer.
- `data.showHoverTooltip,hoverLabels[],hoverUnit` → hover tooltip rows (label/value/unit/color per series).
- `data.sampling` + `data.onSamplingChange` (+ `samplingPresets/showSamplingCalendar/showSamplingFooterSummary/samplingApplyLabel/samplingCancelLabel/samplingDialogAria`) → `SamplingPicker` — **renders only when BOTH present**; a function cannot ride a JSON payload, so the fill's `withDateControl` (shared `fill/shared/sampling-window.ts`) injects `sampling: defaultSampling()` + `onSamplingChange = (next)=>onDateChange(samplingToWindow(next))`.

**Closed vocabularies**:
- Legend-label STRING IDENTITY is the interaction key: series lines, the expected band, and event dots dim/focus by exact label equality. Fallback literals `'Expected Range'`, `'Swell events'`, `'Sag events'` (payload can rebind via `expectedRangeKey`/`eventTypeKeys` but they MUST stay byte-equal to legend labels).
- Event severity classification: `value >= expectedMax → swell else sag` — logic frozen, not payload-selectable.
- Legend swatch derivation when `swatch` unset: `shape==='dot' → 'dot'`, `label==='Expected Range' → 'square-filled'`, else `'square'` (label-keyed).
- `availability`/`cardLoading` loading unions; axis styling (cream/teal AXIS_STYLE) frozen.
- Host sampling vocabulary: `samplingToWindow` maps PresetId `today|yesterday|last-7-days|this-month|last-month|custom` → host `{range, sampling(2hour|shift|day|week|hourly), start, end}` — a closed switch.

**State/interactions**: `useInteractiveLegend` (series focus/dim, local); `useState hoverIndex` (opt-in tooltip); header SamplingPicker → per-card re-fetch through host `onDateChange` (cards 67/69 only DG cards with a real re-fetch loop).

**Title**: single payload string `data.title`.

**Fill guard-rails**: usability probe `Array.isArray(data.series)` else `unavailableHistory(...)`; `sanitizeHistory` guarantees all mapped arrays, finitizes scaled scalars, `'—'` bucket → null gap, drops non-finite ref-lines.

---

### 2.3 LiveOpsCard — card 70 (COMPONENTS tier)
`/home/rohith/CMD_V2/src/pages/assets/diesel-generator/tabs/operations-runtime/LiveOpsCard.tsx` (105 ln)

**Primitives mounted**: thin adapter over **`ProgressKpiCard`** (headline + `TickProgressSegment[]` progress bar + marker + 2 × `KpiStatStrip` sections + insight footer) with `StatusBadge` header action. Loading branch: `Card`+`CardHeader`+`CardBodySkeleton kpiCells={4} legendRows={1}`.

**payload → primitive mapping** (props `{ view: LiveOpsView }`; payload `{variant, view}` unwrapped by `registry/unwrap.ts` aliasing):
- `view.title` → ProgressKpiCard title; `view.state.{label,tone}` → StatusBadge.
- `view.service.hours.toFixed(0)` + `service.ceiling` → headline value/target; unit `UNITS.hours` + suffix `DESCRIPTORS.toService` (frozen); meta = `` `${PRESENTATION_LABELS.avail} ${service.availability.toFixed(1)}%` ``.
- `view.service.fraction` → `servicePct` → 2 progress segments (used/remaining); `service.warnPct` → marker; `SERVICE_BAR_TONE[service.tone]` → segment color.
- `view.topKpis[]` and `view.stateKpis[]` (`KpiCell {id,label,value,unit,swatch}`) → two `KpiStatStrip` strips via `toKpiStatCells`.
- `view.insight` → footer.

**Closed vocabularies**: `SERVICE_BAR_TONE: Record<StatusTone(success|warning|fail|critical|info|neutral),color>`; headline unit/suffix/meta words (`UNITS.hours`, `DESCRIPTORS.toService`, `PRESENTATION_LABELS.avail`) are registry constants, not payload; unguarded numerics `service.hours/.availability/.fraction` (`.toFixed` — host `guardPayload` finitizes before spread).

**State/interactions**: none (only the `loading` prop seam).

**Title**: `view.title` payload string.

---

### 2.4 EnergyReliabilityCard — card 72 (COMPONENTS tier)
`/home/rohith/CMD_V2/src/pages/assets/diesel-generator/tabs/operations-runtime/EnergyReliabilityCard.tsx` (73 ln)

**Primitives mounted**: adapter over **`ProgressKpiCard`** (headline + active/reactive progress split + 1 × `KpiStatStrip` + insight). Loading: `Card`+`CardHeader`+`CardBodySkeleton kpiCells={4}`.

**payload → primitive mapping** (props `{ view: EnergyReliabilityView }`):
- `view.apparentMvah.toFixed(1)` → headline value, unit `UNITS.energyMvah`; meta = `` `${PRESENTATION_LABELS.pf} ${view.pf.toFixed(2)}` ``.
- `view.activeFraction`/`view.reactiveFraction` → progress segments colored `SERIES_COLOR.active/.reactive` (tab tokens.ts — frozen).
- `view.cells[] KpiCell` → KpiStatStrip (Active/Reactive/MTBF/MTTR); `view.insight` → footer.

**Closed vocabularies**: segment ids/colors fixed (`SERIES_COLOR`); unit/meta words fixed; unguarded `.toFixed` on apparentMvah/pf.

**State/interactions**: none. **Title**: `view.title`.

---

### 2.5 RuntimeDutyPanel — card 71 (FILL)
`/home/rohith/CMD_V2/src/pages/assets/diesel-generator/tabs/operations-runtime/RuntimeDutyPanel.tsx` (421 ln)

**Primitives mounted**: `Card` → `CardHeader` (title + **`SamplingPicker`** action w/ `SAMPLING_RESOLUTION_OPTIONS` from tab config) → body grid `1fr | 235px`: LEFT **`KpiStatStrip`** + DutyChartArea = **`ResponsiveSvg`→`ChartFrame`** → [**`GridAxis`** (dual-Y: "Run h" left / "%" right — labels hard-coded), **`StackedBars`** (one segment per bucket), **`LinePath`** (load %, smooth), transparent `<rect>` hit areas per bucket]; RIGHT RunsColumn = header (`runs.headerLabel` + **`StatusPill`** "{N} STARTS" or "CLEAR" button) + **`DataTable`** (3 columns, custom cell renderers, sticky header, `emptyState` "No runs in this period"). Axis math via **`buildChartDomain`**. Loading: `CardBodySkeleton kpiCells={3} rail railRows={6}`.

**payload → primitive mapping** (props `{duty: DutyView, runs: RunsView, selectedBucket, onSelectBucket, sampling, onSamplingChange}`; fill supplies `duty = payload.duty ?? emptyVm().duty`, `runs = emptyVm().runs` ALWAYS — run log has no neuract source):
- `duty.title` → CardHeader.
- `duty.topKpis[] DutyTopKpi {id,label,value,unit,sub}` → KpiStatStrip.
- `duty.points[] {label,runHours,loadPct,starts}` → bars from `p.runHours`, line from `p.loadPct`, x-ticks from `p.label` every `duty.tickInterval`.
- `duty.series[] DutySeriesDef` is carried on the payload but **NOT used by the panel** to select fields — the chart hard-reads `runHours`/`loadPct` (closed accessors). `duty.demandLimitKw` also unused here (belongs to card 73's view).
- `runs.rows[] RunEvent {clock,bucket,duration,loadAvg,fault,statusWord}` → DataTable rows (2-line clock+meta cell; `duration.toFixed(2)` h; `loadAvg` %; `fault` flips row tint/destructive text); `runs.columnLabels {start,dur,load}` → column headers (labels payload-bound, accessors fixed); `runs.headerLabel` / `runs.totalStarts` → right-column header + STARTS pill.
- `selectedBucket` dims non-selected bars (`SURFACE.divider` vs `SERIES_COLOR.runHours`).

**Closed vocabularies**: column ids + row-field accessors (`clock,bucket,statusWord,duration,loadAvg,fault`); axis titles "Run h"/"%"; pill qualifier `' STARTS'` and `"CLEAR"` literal; empty-state string; `SERIES_COLOR.runHours/.load` tokens; sampling resolution options from tab `config.ts`; pct axis pinned 0..100.

**State/interactions** (held in the FILL wrapper `card-71.tsx`): `useState sampling` (default `DEFAULT_SAMPLING_SELECTION` from tab config) — SamplingPicker Apply → `onDateChange(samplingToWindow(next))` (host re-fetch, currently no-op); `useState selectedBucket` — bucket click filter (guarded to null when `duty.points` empty); CLEAR resets.

**Title**: `duty.title` payload string.

---

### 2.6 PowerEnergyAnalysisPanel — card 73 (FILL; **already a shared primitive**)
`/home/rohith/CMD_V2/src/components/charts/primitives/PowerEnergyAnalysisPanel.tsx`

**Primitives mounted** (internally): `Card` → `CardHeader` (title + **`SamplingPicker`** + **`SegmentedControl`** Active/Reactive/Demand) → LEFT **`KpiStatStrip`** (4 computed tiles) + chart (**`ResponsiveSvg`/`ChartFrame`/`GridAxis`/`StackedBars`/`ReferenceLine`** limit line) ; RIGHT rail **`InteractiveLegendRow`** rows + **`AiSummary`**. Axis via `buildChartDomain`.

**payload → primitive mapping** (props `{buckets, selIdx, limitKw, title?, sampling?, onSamplingChange?}`; fill card-73 is **metadata-only**: `powerEnergyView()` returns `{buckets: [], limitKw: DEMAND_LIMIT_KW}` — the FE nameplate const from tab config; the Layer-2 payload is IGNORED (`payload: _payload`), since card 73 has no card_payloads story):
- `buckets[] {label,demand,active,reactive}` → bars per mode; KPI tiles + the insight sentence are COMPUTED INSIDE the primitive (`totActive/totReactive/peakDemand` reductions, `/1000` MWh conversion, over/near-limit narrative) — a ported generic card must reproduce or bypass this in-primitive aggregation.
- `limitKw` → dashed `ReferenceLine` (demand mode) + "Limit" KPI tile.

**Closed vocabularies**: mode union `'active'|'reactive'|'demand'` with frozen `MODE_OPTIONS` labels + `MODE_COLOR`; demand band thresholds 90/100% (`demandBand`) + `BAND_COLOR`; KPI tile labels from `PRESENTATION_LABELS`; default title `'Power Energy Analysis'`; insight template string frozen.

**State/interactions**: internal `useState mode` (SegmentedControl); internal-or-controlled sampling; demand-band legend focus (`useInteractiveLegend`); fill holds `sampling` + `selIdx` (guarded null on empty buckets); header title gains ` · {bucketLabel}` when a bucket selected.

**Title**: `title` prop (default literal) — fill passes none.

---

### 2.7 Panel (EngineHistoryCharts) — cards 61 (thermal) / 62 (mech)
`/home/rohith/CMD_V2/src/pages/assets/diesel-generator/tabs/engine-cooling/EngineHistoryCharts.tsx` (172 ln) + `EngineSvgChart.tsx`

**Primitives mounted**: `Card` → `CardHeader` (title + **`EngineDatePicker`** — cosmetic, no props) → LEFT **`KpiStatStrip`** + `SvgChartBody` (**`ResponsiveSvg`→`ChartFrame`** with **`GridAxis`**, **`LinePath`** per series, **`HorizontalBand`** expected band, **`ReferenceLine`** warn/trip, **`EventDot`**, plain `<rect>` run-state mode bands, hover from `EngineHoverProvider` context) ; RIGHT rail: **`InteractiveLegendRow`** list, **`EventSeverityFilter`**, local `EventCard` chips, `ModeLegendMini` (frozen run-state key), **`AiSummary`**. Loading: `CardBodySkeleton kpiCells={3} rail railRows={6}`.

**payload → primitive mapping** — props `{vm: EngineCoolingViewModel, chart: ChartVM}`. The Layer-2 payload carries ONLY a `chart` slice `{title,kpis,axes,band,legend,events,insight}`; the fill (`dg-engine-cooling/view-model.ts`) builds CMD V2's typed-empty vm via the REAL `buildEngineCoolingViewModel(emptyEngineFrame())` (exactly ONE all-zero point — an empty array crashes the KPI builder: `points[points.length-1]`, `Math.max(...)`), then `mergeChart` overlays payload fields onto `vm.charts[thermal|mech]`:
- `chart.title` → CardHeader; `chart.kpis[] EngineKpi {label,value,unit,note,swatch,valueColor,unitColor,subColor}` → KpiStatStrip.
- `chart.legend[] {label,value,unit,separator,color,swatch}` → InteractiveLegendRow rail (labels = focus keys).
- `chart.events[] EngineEvent {series,idx,severity,title,label,why,value,unit}` → EventCard chips + chart EventDots; severity counts feed `EventSeverityFilter`.
- `chart.axes/band` → GridAxis/HorizontalBand; `chart.insight` → AiSummary.
- **Plotted values come from `vm.points` (fixed field names `coolant,oilTemp,intake,exhaust,oilPressure,speedPct,loadPct,speedRaw,runState`) — NOT payload-bindable**; the fill keeps `series: base.series` (empty-vm descriptors) so legend/series stay consistent with empty points.
- Fill drops the builder's fabricated zero-event insight ("All temperatures held the expected band…") unless the payload carried its own `chart.insight`.

**Closed vocabularies**: `ChartId` union `'thermal'|'mech'` (fill selects per card_id); series keys/axes from tab `config.ts` (`seriesFor/axesFor/bandFor`); severity union `'warn'|'danger'` (`SEV` record); `RunState` union `'running'|'warm-up'|'cooldown'|'off'` (`RUN_FILL`/`RUN_TEXT` records + frozen ModeLegendMini list); `AXIS_UNIT` record keyed `temp|exh|kpa|pct`; literals "No events in this view", "Run state".

**State/interactions**: `useInteractiveLegend` (legend isolates lines AND filters event cards via `labelToKey` from config `legendLabel`); `useState eventView ('all'|'warn'|'danger')`; `EngineHoverProvider` synced crosshair/tooltip; `EngineDatePicker` purely cosmetic (fill wires no onDateChange — no re-fetchable endpoint for engine telemetry).

**Title**: `chart.title` (payload overlay, else the builder's `CHART_TITLES[chartId]` config default).

---

### 2.8 FuelTankAnatomy — card 63
`/home/rohith/CMD_V2/src/pages/electrical/lt-pcc/tabs/dg-overview/FuelTankAnatomy.tsx` (351 ln)

**Primitives mounted**: NOT a chart card — a three.js **`Canvas`** (@react-three/fiber + drei `OrbitControls`/`useGLTF` on `/models/DG_v1.glb`, fuel node matched by `/fuel/i`), 3 local `ChannelCard` buttons, and **`AiSummary`** at the bottom. Only chart-system primitives used: `AiSummary`, `presentationLabel`, `UNITS`, `CHART_COLORS` tokens.

**payload → primitive mapping** (props `{snapshot: FuelSnapshot, display?: FuelTankDisplay}`; payload `{snapshot, display}` IS the props; fill `tankSnapshot` finitizes the 5 fields):
- `snapshot.fuelLevel` → 3D fill height (`fillPct`, clip-plane) AND channel value `.toFixed(0)` %; `snapshot.fuelRate` → flow channel (L/hr); `snapshot.fuelTemp` → temperature channel (°C) — **`.toFixed(0)` with NO null guard** (why the fill finitizes '—'→0); `snapshot.autonomy/efficiency` consumed only by display-default resolution.
- `display.{title,subtitle,channelDetail{level,flow,temperature},aiText}` → header/prose/`AiSummary`, resolved per-field against byte-identical `resolveFuelTankDisplay` defaults when `display` undefined.

**Closed vocabularies**: `FuelEffectId` union `'level'|'flow'|'temperature'` (`CHANNEL` color record, `waveAmp`, pulse branches); channel labels from `presentationLabel('fuelLevel'|'fuelRate'|'fuelTemp')`; `levelTone`/`tempTone` thresholds in `fuelTankDisplay.ts`; GLB path + node regex frozen.

**State/interactions**: `useState activeId` (channel card click recolors/animates the 3D fill); OrbitControls autorotate/zoom. No date control. **SSR hazard**: fiber Canvas needs DOM/WebGL — fill card-63 returns an empty shell when `typeof window === 'undefined'`.

**Title**: `display.title` else resolver default (with `resolved.subtitle` beneath; active-channel chip at right).

---

### 2.9 RunsList (FuelHistoryCharts) — card 64
`/home/rohith/CMD_V2/src/pages/assets/diesel-generator/tabs/fuel-efficiency/FuelHistoryCharts.tsx` lines 43–106

**Primitives mounted**: header block (title + aggregate-stats subtitle + "{starts} starts" chip — local JSX) + **`DataTable`** (6 columns, sticky header, scrollBody, emptyState "No runs in this period"). Loading: `ListBodySkeleton rows={5}`.

**payload → primitive mapping** (props `{runs: FuelRun[], stats: RunsStats}`; fill passes `runs = []` ALWAYS — no neuract source — and `stats = payload.stats ?? emptyVm().runsStats`):
- `stats.title` → header; `stats.{avgLoad,runHours,totalFuelL,totalKwh,faults,starts}` → subtitle line (`runHours.toFixed(1)`, `(totalKwh/1000).toFixed(1)` MWh — **unguarded `.toFixed`**, fill guarantees zero-valued stats) + starts chip.
- `stats.columnLabels {start,dur,load,fuel,kwh,sfc}` → DataTable headers; row accessors fixed: `r.clock/r.agoLabel/r.fault` (start cell), `r.duration` h, `r.loadAvg` %, `r.fuelL` L, `r.kWh`, `r.sfc.toFixed(2)`; `r.fault` flips row tint (`RESERVE.chipBg`) + text color.

**Closed vocabularies**: column id set + row field names; literal "No runs in this period"; `'{n} starts'` chip; `' fault(s)'` suffix grammar; RESERVE/stone color tokens.

**State/interactions**: none; no date control.

**Title**: `stats.title` payload string.

---

### 2.10 FuelCompositeCard (FuelHistoryCharts) — card 65
same file, lines 112–204, + `FuelSvgChart.tsx`

**Primitives mounted**: `Card` → `CardHeader` (title + cosmetic **`EngineDatePicker`**) → **`KpiStatStrip`** → **`StateStripChartFrame`** (mode strip INSIDE the chart box, cells vertex-aligned; xLabels below) wrapping `SvgChartBody` (**`ResponsiveSvg`/`ChartFrame`/`GridAxis`/`LinePath`/`HorizontalBand`/`ReferenceLine`/`EventDot`**, hover via `FuelHoverProvider`) → bottom row of **`InteractiveLegendRow`** + frozen fuel-mode key → **`AiSummary`**. Loading: `CardBodySkeleton kpiCells={4} legendRows={2}`.

**payload → primitive mapping** (props `{vm: FuelEfficiencyViewModel}`; Layer-2 payload carries only `{chart}`; fill `fuelCompositeVm` overlays it on `buildFuelEfficiencyViewModel(emptyFuelFrame())` — empty points [] are legal here, unlike engine-cooling):
- `vm.chart.title` → CardHeader; `vm.chart.kpis[]` (adds `prefix` e.g. "₹") → KpiStatStrip; `vm.chart.legend[]` → legend rows; `vm.chart.insight` → AiSummary ("No fuel data in this window." on empty).
- `vm.points[] {mode,…level/rate/temp fields}` → plotted series + `MODE[p.mode]` strip cells; `vm.ticks`/`vm.count`/`vm.labelAt` → x labels. **Points NOT payload-bindable** (fuel telemetry absent from neuract; fill keeps them empty and keeps `series: base.series`).

**Closed vocabularies**: `FuelMode` union `'running'|'refuel'|'idle'|'low'` (`MODE` record + frozen bottom key + "Mode" literal); axis-label record `{pct,rate}`; `RESERVE_PCT` low-fuel threshold from config; KPI/legend/mergeChart array keys same closed set as engine-cooling (`title,kpis,axes,band,legend,events,series,insight`).

**State/interactions**: `useInteractiveLegend` (legend dims lines); `FuelHoverProvider` crosshair/tooltip; EngineDatePicker self-contained cosmetic → no onDateChange.

**Title**: `vm.chart.title`.

---

## 3. Payload-shape → primitive-family DISPATCH keys (generic port analysis)

The DG payloads carry **no `pres` block** (unlike panel-overview cards where `pres.stackSeries/stackOrder` → timeline and `pres.tiles+tileOrder` → PqTopStrip tile grid, cf. `cmd/section-split.tsx` + `cmd/guards/strip-controls.ts`). Every DG payload is already component-props-shaped, one single-purpose key deep. The shape keys below are the discriminants a generic pres-dispatcher could key on:

| payload signature (post-unwrap) | cards | generic primitive family |
|---|---|---|
| `data.metrics[] + data.phases[] (+ summary/band/status)` | 66, 68 | **KPI-strip + phase-bar rows snapshot** → `KpiStatStrip` + `PhaseValueRows`/bar rows; `summary`→hero tile, `band.markerPct`→deviation meter |
| `data.series[].values + data.legend[] + data.stats[] + minY/maxY/yTicks/xLabels + expectedMin/Max + maxLine/minLine + events[]` | 67, 69 | **multi-line history timeline** → `ChartFrame+GridAxis+LinePath+HorizontalBand+ReferenceLine+EventDot` with `KpiStatStrip` header + `InteractiveLegendRow` rail; `sampling` presence → SamplingPicker |
| `view.topKpis/stateKpis|cells + view.service.fraction|activeFraction/reactiveFraction + insight` | 70, 72 | **progress-KPI card** → `ProgressKpiCard` (headline value/unit/meta, segments from fractions, kpiStrips from KpiCell[], insight) |
| `duty.points[]{label,runHours,loadPct} + duty.topKpis + runs.rows/columnLabels` | 71 | **bar+line dual-axis chart + DataTable rail** → `KpiStatStrip + StackedBars + LinePath + GridAxis` left, `DataTable` right; `duty.series[]` is the ready-made series-descriptor vocab a generic port SHOULD honour (the current panel ignores it and hard-codes field names) |
| `buckets[]{label,demand,active,reactive} + limitKw` | 73 | **PowerEnergyAnalysisPanel is itself the shared primitive** — direct pass-through; generic dispatch = presence of `buckets`+`limitKw` |
| `chart{title,kpis,axes,band,legend,events,insight}` (series values live in vm.points, not payload) | 61, 62, 65 | **composite chrome-over-timeline** → `KpiStatStrip` + SVG timeline + legend rail + `EventSeverityFilter` + `AiSummary`; generic port could dispatch on `chart.kpis+chart.legend+chart.axes`; the per-tab `vm.points` field unions are the blocker — a generic timeline needs the series VALUES on the payload (`series[].values` like HistoryPanelData), not module-typed points |
| `stats{title,columnLabels,aggregates} (+ runs[])` | 64 | **stats-header + DataTable** → header tiles from aggregates, `DataTable` columns generated from `columnLabels` record keys |
| `snapshot{fuelLevel,fuelRate,fuelTemp,…} + display{title,subtitle,channelDetail,aiText}` | 63 | **asset_3d anatomy family** (channel-tile + 3D viewer + `AiSummary`) — belongs with the SPECIAL/asset_3d envelope family, not a chart primitive |
| envelope `{object|viewer|template}` keys | 60 | already dispatched generically by `isAsset3dEnvelope` detection |

**Cross-cutting port notes**
1. **Interaction identity = legend-label byte-equality** (HistoryPanel, engine/fuel Panels): a generic renderer must preserve label→series→event key wiring; payload rebinding hooks already exist (`expectedRangeKey`, `eventTypeKeys`).
2. **Functions can't ride payloads**: every SamplingPicker only mounts when the fill injects `onSamplingChange`; generic port needs a declarative flag (e.g. `pres.dateControl: 'sampling'`) + host-side `samplingToWindow` (two translator dialects exist: `fill/shared/sampling-window.ts` and `dg-operations-runtime/date-wiring.ts` resolutionToSampling).
3. **In-primitive computation** (PowerEnergyAnalysisPanel KPI/insight; RunsList subtitle) recomputes derived numbers from raw rows — generic ports must feed raw buckets, not pre-aggregates.
4. **Typed-empty seeds are load-bearing**: engine-cooling needs ≥1 all-zero point (crash otherwise); fuel accepts []; V&C needs `unavailableHealth/History` structured-empties. A primitives-only port must keep per-family empty-state contracts.
5. **Unguarded numeric leaves** (`.toFixed` on service.hours, apparentMvah, runHours, snapshot.fuelLevel, duration) rely on host `guardPayload` + fill finitizers — the port must keep a finitize pass.
6. **Titles in this family are single payload strings** (`data.title` / `view.title` / `duty.title` / `chart.title` / `stats.title` / `display.title`); no `titlePrefix/titleConnector/period.label` composition (that machinery is feeder-family). Card 73 is the only default-literal title (`'Power Energy Analysis'` + ` · {bucket}` suffix).
