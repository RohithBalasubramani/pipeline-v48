# Primitives inventory — TRANSFORMER card family (cards 74–81)

Scope: host barrel `host/web/src/cmd/components/transformer.ts` + the two FILL barrels that shadow it.
CMD_V2 source root: `/home/rohith/CMD_V2/src` (`@cmd-v2`). Written 2026-07-12 for the primitives-only render port.

---

## 1. COMPONENTS barrel — card_id → CMD_V2 page-card component

`host/web/src/cmd/components/transformer.ts` ("TRANSFORMER asset-dashboard family barrel (cards 74–81, direct payload render, vm prop)"):

| card_id | Component | CMD_V2 source path (`/home/rohith/CMD_V2/src/...`) |
|---|---|---|
| 74 | `ThermalLifeCard` | `pages/assets/transformer/tabs/thermal-life/ThermalLifeCard.tsx` |
| 75 | `LifeCapacityCard` | `pages/assets/transformer/tabs/thermal-life/LifeCapacityCard.tsx` |
| 76 | `ThermalTimelineCard` | `pages/assets/transformer/tabs/thermal-life/ThermalTimelineCard.tsx` |
| 77 | `InsulationAgingCard` | `pages/assets/transformer/tabs/thermal-life/InsulationAgingCard.tsx` |
| 78 | `TapPositionCard` | `pages/assets/transformer/tabs/tap-rtcc/TapPositionCard.tsx` |
| 79 | `VoltageRegulationCard` | `pages/assets/transformer/tabs/tap-rtcc/VoltageRegulationCard.tsx` |
| 80 | `RecentTapChangesCard` | `pages/assets/transformer/tabs/tap-rtcc/RecentTapChangesCard.tsx` |
| 81 | `TapActivityCard` | `pages/assets/transformer/tabs/tap-rtcc/TapActivityCard.tsx` |

## 2. FILL shadowing — every one of the 8 ids is shadowed

`cmd/registry.tsx` resolution order: **FILL[id] WINS over COMPONENTS[id]** ("letting COMPONENTS shadow FILL bypassed every guard the fill was built to apply", 2026-07-06). So at render time none of these cards go through the COMPONENTS direct-spread path; all 8 render through fill fns of signature `(payload, frame?, onDateChange?) => ReactNode`.

| card_id | FILL barrel | per-card file | payload slice consumed |
|---|---|---|---|
| 74 | `cmd/fill/transformer-thermal-life.tsx` | `transformer-thermal-life/card-74.tsx` | `payload.thermalLife` → `thermalLifeVM()` |
| 75 | `cmd/fill/transformer-thermal-life.tsx` | `transformer-thermal-life/card-75.tsx` | `payload.lifeCapacity` → `lifeCapacityVM()` |
| 76 | `cmd/fill/transformer-thermal-life.tsx` | `transformer-thermal-life/card-76.tsx` | `payload.timeline` → `timelineVM()` |
| 77 | `cmd/fill/transformer-thermal-life.tsx` | `transformer-thermal-life/card-77.tsx` | `payload.aging` → `agingVM()` |
| 78 | `cmd/fill/transformer-tap-rtcc.tsx` | `transformer-tap-rtcc/card-78.tsx` | `payload.tapPosition` → `tapPositionVM()` |
| 79 | `cmd/fill/transformer-tap-rtcc.tsx` | `transformer-tap-rtcc/card-79.tsx` | `payload.regulation` → `regulationVM()` |
| 80 | `cmd/fill/transformer-tap-rtcc.tsx` | `transformer-tap-rtcc/card-80.tsx` | `payload.changes` → `tapChangesVM()` |
| 81 | `cmd/fill/transformer-tap-rtcc.tsx` | `transformer-tap-rtcc/card-81.tsx` | `payload.activity` → `activityVM()` |

Shared fill mechanics (both `view-model.ts` files):
- Slice unwrap: `p[key] ?? p.vm ?? p.data ?? p.payload ?? p` — the L2 payload is the harvested Storybook args `{ variant, <slice>: <slice>VM }`; **the payload slice IS the card's `vm`** (passed straight as `vm={…}`), sanitized per-leaf (`fin()` finitizes every `.toFixed`/axis-math scalar, `domain()/axis()` guards `{min,max,ticks}`).
- Honest-empty fallback: unusable slice → the tab's OWN typed-empty view-model, built by running the REAL producer (`buildThermalLifeViewModel` / `buildTapRtccViewModel`) over a 1-bucket zero scaffold, then blanking measured values (points→[], KPI/legend→`'—'`). Never `return null`, never a seed number.
- Date wiring: cards 76/77/79/81 forward the in-card `SamplingPicker`'s `onRequest(chartKey, params)` → `reqToDateWindow`/`chartParamsToDateWindow` → host `DateWindow {range, sampling}` per-card re-fetch (`onDateChange`). Cards 74/75/78/80 have no date control (2-arg fills).
- `frame` arg is always empty — host-served is RETIRED; payload is the only data source.

---

## 3. Per-component primitive inventory

All primitives import from `components/charts/primitives` (`Card`, `CardHeader`, `StatusPill`, `FillBar`, `KpiStatStrip`, `AiSummary`, `SegmentedArcGauge`, `DataTable`, `ChartFrame`, `GridAxis`, `ChartBars`, `LinePath`, `ReferenceLine`, `HorizontalBand`, `ResponsiveSvg`, `InteractiveLegendRow`, `SamplingPicker`, `useInteractiveLegend`, `sparseTickIndexes`, `composeValueUnit`, `composeMetricHeader`, `CardBodySkeleton`, `ListBodySkeleton`, plus token records `CHART_COLORS`, `SURFACES`, `UNITS`, `PRESENTATION_LABELS`).

VM shapes: `thermal-life/types.ts` (`ThermalLifeCardVM`, `LifeCapacityCardVM`, `ThermalTimelineVM`, `InsulationAgingVM`) and `tap-rtcc/types.ts` (`TapPositionCardVM`, `TapChangesCardVM`, `RegulationCardVM`, `ActivityCardVM`).

### Card 74 — ThermalLifeCard (`vm: ThermalLifeCardVM`)

**Primitives / arrangement:** `Card` (24px gutter) → `CardHeader` (+`StatusPill` action) → headline value + **`FillBar`** (thermal-stress bar with marker) as the flex-1 block → bottom-anchored `KpiStatStrip` → `AiSummary` (compact), each opened by a dashed rule. `CardBodySkeleton` when `loading`.

**Payload → primitive:**
- Header: `vm.title`, `vm.status.{label,tone}` → `StatusPill`.
- Bar: `vm.stressPct` → `FillBar pct`, `vm.stressBorderPct` → `marker.pct` + printed under the bar via `composeValueUnit(String(vm.stressBorderPct), UNITS.percent)`; caption `vm.stressBorderLabel`.
- Strip: `vm.metrics.map(m => ({ id: m.label, label: m.label, value: m.value, unit: m.unit, status: { label: m.statusLabel, tone: m.tone } }))` → `KpiStatStrip cells` (`height="auto" flushEnds`).
- Footer: `vm.insight` → `AiSummary text`.

**Closed vocab:** headline label is the fixed `PRESENTATION_LABELS.thermalStress`; denominator literal `/100` and bar endpoints `0` / `100%` hard-coded; all colors from tokens `STRESS_BAR.{track,fill,fillHigh,marker}` — a payload cannot rebind colors or the metric-cell field mapping (`label/value/unit/statusLabel/tone` only).

**State/interactions:** none (props `vm`, `loading` only). **Title:** `CardHeader title={vm.title}` — a single payload string (viewModel seeds it with `PRESENTATION_LABELS.thermalLife`); no prefix/connector/period composition.

### Card 75 — LifeCapacityCard (`vm: LifeCapacityCardVM`)

**Primitives / arrangement:** `Card` → `CardHeader` (+`StatusPill`) → exactly **two local `BarGroup`s** (headline `value /denom+unit label` → `FillBar` → caption), separated by a dashed rule. `ListBodySkeleton rows={2}` when loading.

**Payload → primitive:**
- Group 1 (life): `vm.lifeRemainingYears.toFixed(1)` value, `/${vm.lifeBaseYears}${vm.lifeRemainingUnit}` denom, `vm.lifeRemainingLabel`, `vm.lifeFillPct` → `FillBar pct`, caption `vm.agingCaption`.
- Group 2 (capacity): `String(vm.deratedLoadKva)` value, `vm.deratedKva`+`vm.deratedUnit` denom, `vm.deratedLabel`, `vm.deratedFillPct` → `FillBar pct`, caption `vm.headroomCaption`.

**Closed vocab:** the two-group arrangement and their field bindings are frozen (cannot add a 3rd bar or rebind which scalar drives which bar); colors token-fixed `LIFE_BAR` / `CAPACITY_BAR`; `lifeRemainingYears.toFixed(1)` demands a finite number (fill finitizes).

**State/interactions:** none. **Title:** `vm.title` string (seeded `PRESENTATION_LABELS.lifeAndCapacity`).

### Card 76 — ThermalTimelineCard (`vm: ThermalTimelineVM`)

**Primitives / arrangement:** `Card` → `CardHeader` with **`SamplingPicker`** action → left: `ResponsiveSvg` → `ChartFrame` → `GridAxis` (dual y) + `ChartBars` (load) + `ReferenceLine` (hotspot warn) + 2–3 × `LinePath` (hotspot, optional oil, dashed efficiency) + hand-rolled crosshair `<line>` + transparent hover-capture `<rect>`; absolute-positioned local `HoverTooltip` div. Right: 200px sidebar of `InteractiveLegendRow`s + `AiSummary`. `ThermalChartSkeleton` when loading.

**Payload → primitive:**
- Points: `vm.points[]` (`TimelinePoint { slot, hotspotC, oilC|null, windingC, loadPct, efficiencyPct }`). X ticks: `sparseTickIndexes(n) → vm.points[i].slot`.
- Left °C axis: `vm.tempAxis.{min,max,ticks}` → `GridAxis yTicks`; right % axis **fixed** `PCT_AXIS_TICKS` 0–100.
- Bars: `p.loadPct` → `ChartBars` (right axis). Lines: `p.hotspotC`, `p.oilC ?? 0`, `p.efficiencyPct` (dashed `5 5`) → `LinePath`.
- Reference: `vm.hotspotWarnC` + `vm.hotspotWarnLabel` → `ReferenceLine`.
- Axis titles: `vm.yAxisLabel`, `vm.rightYAxisLabel`.
- Legend: `vm.legend[] { key, label, value, unit, color, swatch }` → `InteractiveLegendRow` (value/unit are display text — split source). Oil series existence: `vm.legend.some(l => l.key === 'oil')`.
- Tooltip rows: switch on `l.key`: `'hotspot' → p.hotspotC.toFixed(1)°C | 'oil' → p.oilC | 'load' → p.loadPct% | else → p.efficiencyPct%`.
- Footer: `vm.insight` → `AiSummary`.

**Closed vocab:** `TimelineSeriesKey = 'hotspot' | 'oil' | 'load' | 'efficiency'` — plotted-series accessors (`p.hotspotC / p.oilC / p.loadPct / p.efficiencyPct`), their mark kind (bar vs line vs dashed line), axis assignment (temps→left, load/eff→right), and tooltip formatting are all keyed to this union; plot colors come from `TIMELINE_SERIES` tokens, NOT from `legend[].color` (legend color is payload-driven, stroke is not). `p.windingC` is carried but never plotted. Right axis pinned 0–100.

**State/interactions:** `useInteractiveLegend(keys)` (click a legend row to focus a series → `opacityFor(key)`), `activeIndex` hover crosshair+tooltip (mouse-x → nearest slot), `sampling` `useState(TIMELINE_DEFAULT_SAMPLING)` controlling the `SamplingPicker` (presets `TIMELINE_PRESETS`, resolutions `TIMELINE_SAMPLING_RESOLUTIONS`); `onChange → onRequest(TIMELINE_CHART_KEY, timelineSelectionToReq(sel))` — the fill maps this to a host `DateWindow` re-fetch. Props: `vm`, `onRequest?`, `loading?`.

**Title:** `vm.title` (seeded `PRESENTATION_LABELS.thermalTimeline`); axis titles composed upstream by `composeMetricHeader` and shipped as plain strings.

### Card 77 — InsulationAgingCard (`vm: InsulationAgingVM`)

**Primitives / arrangement:** `Card` → `CardHeader` + `SamplingPicker` → chart column = **`KpiStatStrip`** (3 cells) over `ResponsiveSvg`/`ChartFrame` (`GridAxis` dual y + `ChartBars` FAA + `ReferenceLine` at 1× + manual SVG `<path>` area fill + `LinePath` LOL + crosshair + hover rect + `HoverTooltip`); right sidebar = `InteractiveLegendRow`s + `AiSummary`. Reuses `ThermalChartSkeleton`.

**Payload → primitive:**
- Points: `vm.points[]` (`AgingPoint { label, faa, lolPct, hotspotPeakC }`). Bars `p.faa` (right ×-axis `vm.faaAxis`), line+area `p.lolPct` (left %-axis `vm.lolAxis`, zoomed window), tooltip extra `p.hotspotPeakC`.
- KPI strip cells (fixed 3): `{ id:'life-used', label: PRESENTATION_LABELS.lifeUsed, value: String(k.lifeUsedPct), sub: k.lifeNote }`, `{ id:'aging-now', value: k.agingFactor.toFixed(1)×, sub: 'vs 1× normal' }`, `{ id:'delta-window', label: 'Δ ${vm.windowDays} days', value: '+${k.deltaLolPct.toFixed(2)}%', valueColor: C.coral500 }` from `vm.kpis {lifeUsedPct, lifeNote, agingFactor, deltaLolPct}` + `vm.windowDays`.
- Reference: pinned `yFaa(1)` with `vm.normalRefLabel`.
- Legend `vm.legend[]` (keys `'lol' | 'faa'`), insight `vm.insight`, axis titles `vm.yAxisLabel/rightYAxisLabel`.
- X labels rendered VERBATIM, thinned to ≤~7 (`labelStep = ceil(n/7)`).

**Closed vocab:** `AgingKey = 'lol' | 'faa'`; accessors `p.faa`/`p.lolPct`/`p.hotspotPeakC` frozen; the 3-cell KPI recipe and its `PRESENTATION_LABELS` (lifeUsed/agingNow/vs1xNormal/lifeConsumed) frozen; tooltip rows fixed (`lossOfLife`, `agingFactor`, `hotspotPeak`); colors `AGING_SERIES` tokens; ref line always at value 1 on the FAA axis. Structural hazard: `areaPath` reads `lolPoints[0].x`/`[last].x` unconditionally — empty points crash (fill floors to a single `'—'` baseline bucket); `k.agingFactor.toFixed(1)` / `k.deltaLolPct.toFixed(2)` must be numeric.

**State/interactions:** `useInteractiveLegend(['lol','faa'])`, hover `activeIndex`, `sampling` `useState(AGING_DEFAULT_SAMPLING)` → `onRequest(AGING_CHART_KEY, agingSelectionToReq(sel))` (this-month × Daily↔Weekly). Props: `vm`, `onRequest?`, `loading?`.

**Title:** `vm.title` (seeded `PRESENTATION_LABELS.insulationAgingLossOfLife`); the "Δ N days" KPI label is the only period-ish composition, built in-card from `vm.windowDays` via `composeValueUnit(String(vm.windowDays), UNITS.days)`.

### Card 78 — TapPositionCard (`vm: TapPositionCardVM`)

**Primitives / arrangement:** `Card` (24px gutter) → `CardHeader` (+`StatusPill`) → centered **`SegmentedArcGauge`** (aspect 200:114 wrapper, flex-1) → bottom-anchored `KpiStatStrip` → `AiSummary` (compact). `CardBodySkeleton` when loading.

**Payload → primitive:**
- Gauge: `vm.gauge.{count, value, optimal}` → `SegmentedArcGauge count/value/optimal` (count = tap wedges, needle on `value`, accent over `optimal`; `optimal: number | null`).
- Strip: `vm.kpis.map(k => ({ id: k.id, label: k.label, value: k.value, valueColor: k.valueColor }))` (Current · Optimal · RTCC mode).
- Header/footer: `vm.status.{label,tone}`, `vm.insight`.

**Closed vocab:** gauge colors token-fixed `GAUGE.{segment,label,needle,optimal}`; KPI cells drop `unit`/`status` (only `id/label/value/valueColor` forwarded); arrangement gauge-over-strip frozen.

**State/interactions:** none (`vm`, `loading`). **Title:** `vm.title` (seeded `PRESENTATION_LABELS.tapPositionOptimization`).

### Card 79 — VoltageRegulationCard (`vm: RegulationCardVM`)

**Primitives / arrangement:** `Card` → `CardHeader` + `SamplingPicker` (with `shiftOptions`/`shiftWhenResolution="shift"`) → chart column = `KpiStatStrip` over `ResponsiveSvg`/`ChartFrame`: **`HorizontalBand`** (AVR dead-band) + `ReferenceLine` (setpoint, placement="below") + `GridAxis` (dual y) + `LinePath curve="step"` (tap, right axis) + `LinePath curve="smooth"` (voltage, left axis) + coral excursion `<circle>` dots + crosshair + hover rect + `HoverTooltip`; sidebar = `InteractiveLegendRow`s + `AiSummary`. `TapChartSkeleton` when loading.

**Payload → primitive:**
- Points: `vm.points[]` (`RegulationPoint { label, voltageKv, tap, excursion }`). Voltage → smooth `LinePath` on `vm.voltageAxis` (2-decimal tick labels `t.toFixed(2)`); tap → step `LinePath` on `vm.tapAxis`; `p.excursion` → dots at `(xAt(i), yV(p.voltageKv))`.
- Band/reference: `vm.bandHighKv`/`vm.bandLowKv` → `HorizontalBand`, `vm.setpointKv` → `ReferenceLine` labeled with fixed `PRESENTATION_LABELS.setPointVoltage`.
- KPIs: `vm.kpis.map(k => ({ id, label, value, unit }))` (Setpoint · Regulation · In-Range time).
- Legend: `vm.legend[]` (keys `'voltage' | 'tap'`, supports `separator`); axis titles `vm.yAxisLabel/rightYAxisLabel`; tooltip excursion tag `vm.outOfBandLabel`; `vm.insight`.
- X: lines-only edge-to-edge `xAt(i) = i/(n-1)`; ticks `sparseTickIndexes`.

**Closed vocab:** `RegKey = 'voltage' | 'tap'`; accessors `p.voltageKv`/`p.tap`/`p.excursion` frozen; mark kinds (smooth vs step), axis sides, tooltip rows (`PRESENTATION_LABELS.voltage` at `.toFixed(2)` kV, `tapPosition`) and ref-line label frozen; colors `REG_SERIES` tokens; tap axis scaled `0..vm.tapAxis.max`.

**State/interactions:** `useInteractiveLegend(['voltage','tap'])`, hover `activeIndex` (nearest-vertex `Math.round`), `sampling` `useState(TAP_DEFAULT_SAMPLING)` → `onRequest(REGULATION_CHART_KEY, tapSelectionToReq(sel))`. Props: `vm`, `onRequest?`, `loading?`. **Title:** `vm.title` (seeded `PRESENTATION_LABELS.voltageRegulationTimeline`).

### Card 80 — RecentTapChangesCard (`vm: TapChangesCardVM`)

**Primitives / arrangement:** `Card` (24px gutter) → `CardHeader` (no action) → **`DataTable`** (cream header 32px, 32px rows, `scrollBody`). `ListBodySkeleton rows={6}` when loading.

**Payload → primitive:**
- Columns built from `vm.columnLabels {time, from, to}` — headers payload-driven ("Column headers come from the payload (vm.columnLabels) so an AI can read/re-word the table"), 3 fixed `DataTableColumn`s: `{ id:'time', render: r => r.time, fit: true, fitMin: 76, fitMax: 110 }`, centered `r.fromTap`, centered `r.toTap`.
- Rows: `vm.rows[]` (`TapChangeRow { time, fromTap, toTap }`), `getRowKey = ${r.time}-${i}`.

**Closed vocab:** exactly 3 columns; row accessors `r.time / r.fromTap / r.toTap` frozen (headers re-wordable, bindings not); `emptyState="No tap changes today"` and `ariaLabel="Recent tap changes"` hard-coded literals.

**State/interactions:** none (`vm`, `loading`). **Title:** `vm.title` (seeded `PRESENTATION_LABELS.recentTapChanges`).

### Card 81 — TapActivityCard (`vm: ActivityCardVM`)

**Primitives / arrangement:** `Card` → `CardHeader` + `SamplingPicker` (shift-capable, same config as 79) → chart column = `KpiStatStrip` over `ResponsiveSvg`/`ChartFrame` (`GridAxis` dual y + `ChartBars` hourly ops + `LinePath curve="step-after"` cumulative counter + crosshair + hover rect + `HoverTooltip`); sidebar = `InteractiveLegendRow`s + `AiSummary`. Reuses `TapChartSkeleton`.

**Payload → primitive:**
- Points: `vm.points[]` (`TapActivityPoint { label, count, cumTotal }`). Bars `p.count` on left `vm.countAxis` (scaled `0..max`); step-after line `p.cumTotal` on right `vm.cumAxis {min,max}`.
- KPIs: `vm.kpis.map(k => ({ id, label, value, unit }))` (Total · Peak · Average).
- Legend `vm.legend[]` (keys `'today' | 'total'`, no unit field); axis titles `vm.yAxisLabel/rightYAxisLabel`; `vm.insight`.

**Closed vocab:** `ActKey = 'today' | 'total'`; accessors `p.count`/`p.cumTotal` frozen; mark kinds/axis sides frozen; tooltip labels fixed `PRESENTATION_LABELS.tapOperations` / `.totalCount`; colors `ACTIVITY_SERIES` tokens.

**State/interactions:** `useInteractiveLegend(['today','total'])`, hover `activeIndex`, `sampling` → `onRequest(ACTIVITY_CHART_KEY, tapSelectionToReq(sel))`. Props: `vm`, `onRequest?`, `loading?`. **Title:** `vm.title` (seeded `PRESENTATION_LABELS.tapActivityWear`).

---

## 4. Cross-cutting notes for the port

- **Title grammar:** this family has NO `titlePrefix`/`titleConnector`/`period.label` composition (unlike the feeder fills' `periodToDateWindow` label path). Every card does `CardHeader title={vm.title}` — one payload string per slice, authored upstream by the viewModel from `PRESENTATION_LABELS`. The only period-aware chrome is card 77's in-card `Δ ${windowDays} days` KPI label.
- **Legend color vs plot color:** in all four chart cards `legend[].color/swatch` come from the payload, but the plotted strokes/fills come from token records (`TIMELINE_SERIES`, `AGING_SERIES`, `REG_SERIES`, `ACTIVITY_SERIES`) — a payload can desynchronize legend and plot colors but can never restyle the plot.
- **Hand-rolled non-primitives** (must be reproduced or promoted in a primitives-only port): the hover crosshair `<line>` + capture `<rect>` + absolute `HoverTooltip` div (all 4 chart cards, same grammar), card 77's manual SVG area `<path>` ("no primitive owns area fills yet"), card 79's excursion `<circle>` dots, the two skeletons (`ThermalChartSkeleton`, `TapChartSkeleton`).
- **Crash surfaces the fills already guard** (the port inherits these contracts): `points[i]` indexing + `.toFixed` on every plotted scalar; card 77 `areaPath` on `points[0]` (never empty); `lifeRemainingYears.toFixed(1)`; `agingFactor.toFixed(1)` / `deltaLolPct.toFixed(2)`; `GridAxis` NaN scaling from non-finite `{min,max}`.
- **Loading:** every card takes `loading?: boolean` and swaps only the body (Card + CardHeader stay mounted).

## 5. Generic pres-vocabulary dispatch (payload-shape → primitive family)

The transformer payloads are VM-shaped (`{ variant, <slice>: VM }`), not the standard `pres.*` vocabulary — but each slice shape maps 1:1 onto a dispatchable primitive family:

| Dispatch key (present in slice) | Primitive family | Family members here |
|---|---|---|
| `points[] + legend[] + 2 axis domains ({min,max,ticks}) + yAxisLabel/rightYAxisLabel` | **dual-axis timeline** (`ChartFrame`+`GridAxis`+`ChartBars`/`LinePath`+`ReferenceLine`+sidebar `InteractiveLegendRow`+`AiSummary`) — the `pres.stackSeries → timeline` analog | 76, 77, 79, 81 |
| `kpis[] ({id,label,value,unit?,sub?,valueColor?})` | **`KpiStatStrip` / MetricTileGrid** — the `pres.tiles + tileOrder` analog | 74 (as `metrics[]`), 77, 78, 79, 81 |
| `rows[] + columnLabels` | **`DataTable`** — the `pres.columns + period.panels` analog | 80 |
| `gauge {count, value, optimal}` | **`SegmentedArcGauge`** | 78 |
| `pct + value/denom pair + caption` (`stressPct`/`lifeFillPct`/`deratedFillPct`) | **`FillBar` meter group** | 74, 75 |
| `status {label, tone}` | **`StatusPill`** header action | 74, 75, 78 |
| `insight` (string) | **`AiSummary`** footer/sidebar | all except 75, 80 |
| `title` (string) | **`CardHeader`** | all 8 |
| `setpointKv + bandLowKv/bandHighKv` / `hotspotWarnC` / implicit `1×` | **`HorizontalBand` + `ReferenceLine`** overlays | 79 / 76 / 77 |

What a generic port additionally needs (the ONLY thing not derivable from the slice shape): a **per-series descriptor** replacing each card's closed series union — `{ key, accessor, mark: 'bar'|'line'|'line-dashed'|'step'|'step-after'|'area', axis: 'left'|'right', color, tooltipFormat }`. Today that record is hard-coded per card (`TimelineSeriesKey`, `AgingKey`, `RegKey`, `ActKey` + their accessor switches); shipping it on the payload (e.g. `pres.series[]`) collapses cards 76/77/79/81 into one generic dual-axis timeline renderer, and 74/75 into a generic FillBar-meter card.
