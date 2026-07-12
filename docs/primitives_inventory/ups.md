# UPS card family (cards 50–59) — primitives-only render port inventory

Sources:
- Host barrel: `host/web/src/cmd/components/ups.ts`
- CMD_V2 root: `/home/rohith/CMD_V2/src` (`@cmd-v2` alias)
- Render path: `host/web/src/cmd/registry/render-cmd.tsx` (5-tier), `registry/unwrap.ts` (single-object-prop unwrap), `guards/composite-sampling.ts` (g13)

## 1. card_id → component map (`host/web/src/cmd/components/ups.ts`)

| card_id | Component | Source path (under `/home/rohith/CMD_V2/src`) | Prop shape |
|---|---|---|---|
| 50 | `BatteryHealthCard` | `pages/assets/ups/tabs/battery-autonomy/BatteryHealthCard.tsx` | `{ data: BatteryHealthVM, loading? }` |
| 51 | `ScoreHistoryCard` | `pages/assets/ups/tabs/battery-autonomy/ScoreHistoryCard.tsx` | `{ data: ScoreHistoryVM, sampling?, loading? }` |
| 52 | `BackupReadinessCard` | `pages/assets/ups/tabs/battery-autonomy/BackupReadinessCard.tsx` | `{ data: BackupReadinessVM, loading? }` |
| 53 | `ScoreHistoryCard` (same as 51 — Backup Readiness History) | `pages/assets/ups/tabs/battery-autonomy/ScoreHistoryCard.tsx` | `{ data: ScoreHistoryVM, … }` |
| 54 | `TransferReadinessCard` | `pages/assets/ups/tabs/source-transfer/TransferReadinessCard.tsx` | `{ data: TransferReadinessVM, loading? }` |
| 55 | `ActivityCard` | `pages/assets/ups/tabs/source-transfer/ActivityCard.tsx` | `{ data: ActivityVM, loading? }` |
| 56 | `CompositeChartCard` (SHARED PRIMITIVE) | `components/charts/primitives/CompositeChartCard.tsx` | `{ title, view: CompositeChartView, sampling, onSamplingChange, onViewChange, … }` |
| 57 | `UpsCapacityCard` | `pages/assets/ups/tabs/output-load-capacity/UpsCapacityCard.tsx` | `{ view: UpsCapacityView, loading? }` |
| 58 | `UpsLoadCard` | `pages/assets/ups/tabs/output-load-capacity/UpsLoadCard.tsx` | `{ view: UpsLoadView, loading? }` |
| 59 | `CompositeChartCard` (reused, Output & Load Capacity) | `components/charts/primitives/CompositeChartCard.tsx` | same as 56 |

Seed payload key shapes (`cmd_catalog.card_payloads`, all single-object-prop `{variant, <key>}`):
50 `batteryHealth` · 51 `batteryHistory` · 52 `backupReadiness` · 53 `backupHistory` · 54 `readiness` · 55 `activity` · 56 `composite` · 57 `capacity` · 58 `load` · 59 `composite`.
`unwrap()` aliases the inner object to **all** of `data`/`vm`/`view` + its own key + spreads its fields, so every prop-name variant is satisfied.

## 2. FILL-tier overlap (FILL shadows COMPONENTS in `render-cmd.tsx` tier 2)

**NONE.** Grep of `host/web/src/cmd/fill/**` (barrels `dg-*`, `feeder-*`, `transformer-*`, `panel-overview-*` + their subfolders) shows no `CARDS` registry key in 50–59. All ten UPS ids render on the COMPONENTS tier: `<Comp {...unwrap(guardPayload(payload))} {...dateProps?}/>`. Generic guards that DO touch this family:
- `guards/composite-sampling.ts` **g13**: a dict with `leftAxis` + `rightAxis` + `series[]` and no `sampling` gets `sampling = { preset: "today", range: null }` injected — this is what lets 56/59 mount at all (the `SamplingPicker` `value` prop is required).
- `date-adapter.ts` spreads `onRangeChange` on `is_history` cards (COMPONENTS-tier only); the UPS cards do not declare that prop, so it is inert.
- `unwrap.ts` also grafts `backendAiSummary` (ignored by these cards) and forwards root `loading:true` (g16) into the components' skeleton branches.

## 3. Per-component inventory

### 3.1 BatteryHealthCard (card 50)
File: `pages/assets/ups/tabs/battery-autonomy/BatteryHealthCard.tsx`

- **Primitives mounted** (all from `components/charts/primitives`): `Card` > `CardHeader`(+`StatusPill` action) > [SOC headline = raw spans, not a primitive] > `FillBar`(h=32) + min/max tick row > `KpiStatStrip` (via `healthMetricCells`) > `AiSummary`(density="compact"). `CardBodySkeleton` when `loading`.
- **Payload → primitive mapping** (`data: BatteryHealthVM`, `pages/assets/ups/tabs/battery-autonomy/types.ts`):
  - `data.title` → `CardHeader.title`; `data.status.{label,tone}` → `StatusPill` via `STATUS_PILL_TONE[data.status.tone]`.
  - Headline: `data.soc` / `data.socUnit` / `/{data.socMax}` / `data.socLabel` (styled spans).
  - `data.socPct` → `FillBar.pct` (`trackColor/fillColor` from local `SOC_BAR` tokens, NOT payload); `data.barTicks.{min,max}` → tick captions.
  - `data.metrics: HealthMetric[]` → `healthMetricCells(metrics)` → `KpiStatStrip.cells` (`{id:label, label, value, unit, unitSuffix, status:{label:statusLabel, tone:STATUS_PILL_TONE[tone]}}`).
  - `data.insight` → `AiSummary.text`.
- **Closed vocabularies**: `StatusTone = 'success'|'warning'|'danger'` (shared/types.ts) mapped through `STATUS_PILL_TONE: Record<StatusTone, StatusPillTone> = {success:'normal', warning:'watch', danger:'alarm'}` (`pages/assets/ups/shared/adapters.ts`) — any other tone string crashes the record lookup (`STATUS_PILL_TONES[undefined]`). Colors/fonts are hard tokens (`tokens.ts`), not rebindable from the payload.
- **Local state / interactions**: none (pure render). `loading` prop swaps the body for `CardBodySkeleton kpiCells={3}`.
- **Title**: `data.title` verbatim — payload-carried, no prefix/connector composition.

### 3.2 ScoreHistoryCard (cards 51 + 53)
File: `pages/assets/ups/tabs/battery-autonomy/ScoreHistoryCard.tsx`

- **Primitives mounted**: `Card` > `CardHeader` (action = `SamplingPicker` when `sampling` prop present, else static "Today" chip) > body row = [`ResponsiveSvg` > `ChartFrame` > (`HorizontalBand`×zones, `GridAxis`, `ReferenceLine`×thresholds, `LinePath`×series, hover crosshair `<line>`, peak `<circle>`, hover-capture `<rect>`)] + right sidebar [`InteractiveLegendRow`×series + `AiSummary`]. Custom HTML `HoverTooltip` overlay. `ChartSkeleton` when `loading`.
- **Payload → primitive mapping** (`data: ScoreHistoryVM`):
  - `data.title` → `CardHeader.title`.
  - `data.zones[] {label,from,to,fill}` → `HorizontalBand` at 8% opacity.
  - `data.yTicks[]/minY/maxY/yLabel/xLabels[]/xLabelIndexes[]` → `GridAxis` ticks + rotated y-title.
  - `data.thresholds[] {label,value,color,labelColor}` → dashed `ReferenceLine`s.
  - `data.watchZoneLabel` → raw `<text>` caption pinned at y=8 inside the plot.
  - `data.series[] {key,label,color,dashed,values[],legendValue}` → one `LinePath` per series (smooth curve, dashed via `strokeDasharray`, dot markers when `values.length<=2`) + one `InteractiveLegendRow` per series (`value=String(legendValue)`, swatch `line-dashed|line-plain`).
  - `data.peak? {index,seriesKey,label,color}` → emphasised dot + label on that series.
  - `data.pointLabels[index]` → hover-tooltip header; tooltip rows = every `series.values[index]` (`Math.round`ed).
  - `data.insight` → sidebar `AiSummary.text`.
- **Closed vocabularies**: essentially none on the data path — series/zones/thresholds are open arrays with per-item colors. Scale math assumes `series[0].values.length` = bucket count for ALL series, and `peak.seriesKey` must match a `series.key`. Fixed layout constants: `MARGIN {top:10,right:14,bottom:26,left:40}`, sidebar width 200px, min plot 200×150.
- **Local state / interactions**: `useInteractiveLegend(keys)` (click legend row → focus/dim series via `opacityFor`); `useState activeIndex` for hover crosshair + tooltip (mouse-x → nearest bucket). Optional `sampling: ScoreHistorySamplingControl {value,onChange,presets,resolutionOptions,shiftOptions}` prop mounts the full `SamplingPicker` (calendar + resolution + shift) — omitted on the direct-payload path, so the static "Today" chip renders (non-interactive).
- **Title**: `data.title` verbatim. Header chip literal `"Today"` is hard-coded fallback text.

### 3.3 BackupReadinessCard (card 52)
File: `pages/assets/ups/tabs/battery-autonomy/BackupReadinessCard.tsx`

- **Primitives mounted**: `Card` > `CardHeader`+`StatusPill` > headline spans > `FillBar`(h=32, `marker` + `badge`) + 3-position tick row > `KpiStatStrip` (no status dots) > `AiSummary`. `CardBodySkeleton` when `loading`.
- **Payload → primitive mapping** (`data: BackupReadinessVM`):
  - `data.title`/`data.status` → header (same tone adapter as 50).
  - Headline: `data.score` `/{data.scoreMax}` `data.scoreLabel`.
  - `data.envelopePct` → `FillBar.pct`; fill color switches `fillLow` when `envelopePct < readyMarkerPct` (token colors); `data.readyMarkerPct` → `FillBar.marker.pct` AND the mid caption `{readyMarkerLabel}: {readyMarkerPct}` positioned at `left:{readyMarkerPct}%`; `data.deltaLabel` + `toneChipColors(data.deltaTone)` → `FillBar.badge`; `data.barTicks.{min,max}` → end captions.
  - `data.metrics` → `healthMetricCells(metrics, {withStatus:false})` → `KpiStatStrip` (no dots).
  - `data.insight` → `AiSummary`.
- **Closed vocabularies**: `deltaTone`/`status.tone` ∈ `'success'|'warning'|'danger'` (same `STATUS_PILL_TONE` + `toneChipColors` record lookups). Bar palette from `ENVELOPE_BAR` tokens — not payload-bindable.
- **Local state / interactions**: none.
- **Title**: `data.title` verbatim.

### 3.4 TransferReadinessCard (card 54)
File: `pages/assets/ups/tabs/source-transfer/TransferReadinessCard.tsx`

Structurally IDENTICAL to BackupReadinessCard (Card > CardHeader+StatusPill > headline > FillBar(marker+badge)+ticks > KpiStatStrip(with dots) > AiSummary), differing only in tokens (`READINESS_BAR`) and field names:
- `data.score` doubles as both the headline AND `FillBar.pct` (no separate pct field); `data.scoreMax`, `data.scoreLabel`.
- `data.readyMarkerPct`/`readyMarkerLabel`/`barTicks`/`deltaLabel`/`deltaTone` — same wiring as 52.
- `data.metrics` → `healthMetricCells(data.metrics)` **with** status dots (Input/Bypass/Sync permissive scores).
- Closed vocab: same 3-tone `StatusTone` records. No local state. Title = `data.title`.

### 3.5 ActivityCard (card 55)
File: `pages/assets/ups/tabs/source-transfer/ActivityCard.tsx`

- **Primitives mounted**: `Card` > `CardHeader` (no pill) > headline spans > **local** `ActivityTicks` (30 flex `<span>` ticks — tab-local, NOT a shared primitive) + start/end caption row > `KpiStatStrip` (no dots) > `AiSummary`. `CardBodySkeleton kpiCells={2}` when `loading`.
- **Payload → primitive mapping** (`data: ActivityVM`):
  - `data.title` → header. Headline: `data.count30d` `/{data.windowDays}` `data.countLabel`.
  - `data.ticks: boolean[]` → `ActivityTicks` (true = event-colored tick, `ACTIVITY.event` vs `.idle` token colors); `data.tickStartLabel`/`tickEndLabel` → below-strip captions.
  - `data.metrics` → `healthMetricCells(metrics,{withStatus:false})` → `KpiStatStrip` (Last Transfer / Lifetime Transfers; `lastTransferDays`/`lifetimeTransfers` also exist as raw numbers on the VM but are rendered only through `metrics`).
  - `data.insight` → `AiSummary`.
- **Closed vocabularies**: tick colors are fixed tokens; boolean-only tick vocabulary. Metric tones same 3-value union (unused here since dots are off).
- **Local state / interactions**: none.
- **Title**: `data.title` verbatim.

### 3.6 CompositeChartCard (cards 56 + 59) — ALREADY a shared primitive
File: `components/charts/primitives/CompositeChartCard.tsx`

- **Primitives mounted**: `Card` > `CardHeader` (action = `SamplingPicker` + `SegmentedControl` view toggle) > `KpiStatStrip`(withCellDividers) > `StateStripChartFrame` wrapping [`ResponsiveSvg` > `ChartFrame` > (`GridAxis` dual-axis, optional `ReferenceLine` floor, `LinePath`×series, crosshair, hover `<rect>`)] + HTML `CompositeTooltip` + HTML `CompositeLegend` (series rows + state legend) > `AiSummary` footer. `CompositeChartSkeleton` when `loading`.
- **Props** (`CompositeChartCardProps`): `title`, `view: CompositeChartView`, `sampling: SamplingSelection` (REQUIRED — g13 injects `{preset:'today', range:null}` on the direct-payload path), `onSamplingChange`, `onViewChange`, optional `presets/resolutionOptions/shiftOptions/shiftWhenResolution`, `loading`.
- **Payload (`view`) → primitive mapping**:
  - `view.title ?? title` → `CardHeader.title` (payload-carried title wins over the prop).
  - `view.kpiCells: ScoreKpiCell[] {id,label,value,unit?,swatch?}` → `toKpiStatCells` → `KpiStatStrip`.
  - `view.points: CompositePoint[]` → per-bucket everything: `p.label` → x-ticks (`sparseTickIndexes`, ≤8, real bucket labels) + tooltip header; `p.mode` → state-strip cell color `MODE_COLOR[p.mode]` + tooltip chip; `p[series.key]` → line y-values (non-finite → line BREAK, not zero).
  - `view.series: CompositeSeriesDef[] {key, axis:'left'|'right', label, color, dashed?, width?, unit?, separator?, decimals?}` → one `LinePath` each + tooltip rows (`composeValueUnit`).
  - `view.leftAxis`/`view.rightAxis {title, domain:[min,max], ticks[]}` → `GridAxis` dual y-axes.
  - `view.floor? {value,label}` → dashed `ReferenceLine` on the LEFT axis.
  - `view.legend: CompositeSeriesLegend[] {id,label,value,unit?,separator?,color,swatch:'solid'|'dashed'}` → HTML legend rows.
  - `view.insight` → footer `AiSummary`.
- **CLOSED vocabularies (the big ones for a port)**:
  - `series[].key` MUST be a numeric key of `CompositePoint` — the interface fixes the union: `readiness | bypassFrequencyHz | inputVoltageV? | bypassVoltageV? | inputCurrentA?` (`key: keyof CompositePoint & string`). A payload cannot plot an arbitrary field name; variant keys silently drop from the tooltip (`typeof v !== 'number'`) and break the line.
  - `points[].mode` ∈ `UpsMode = 'normal'|'bypass'|'on-battery'` → `MODE_COLOR` record lookup (unknown mode → `undefined` color) + `modeLabel()` if/else. State legend iterates the HARD-CODED array `['normal','bypass','on-battery']`.
  - `view.activeView` ∈ `CompositeView = 'transfer-score-frequency'|'voltage-current'`; `COMPOSITE_VIEW_OPTIONS` (the SegmentedControl labels) are module constants — not payload-bindable.
  - `SAMPLING_RESOLUTION_OPTIONS` default = Hourly|Daily; series/floor colors offered via `COMPOSITE_SERIES` tokens but consumers pass colors explicitly, so color IS payload-bindable here.
- **Local state / interactions**: `useState activeIndex` (hover crosshair + tooltip); header `SamplingPicker` (controlled by `sampling`/`onSamplingChange`) and `SegmentedControl` (controlled by `view.activeView`/`onViewChange`). On the V48 direct-payload path the callbacks are **undefined** → render-safe, but a user CLICK on the view toggle or picker apply calls `undefined(...)` (interaction-time hazard; render only, no crash on mount thanks to g13's `sampling` default).
- **Title**: `view.title ?? title` — for 56/59 the payload inner `composite.title` is spread AND aliased so both resolve from the payload.

### 3.7 UpsCapacityCard (card 57)
File: `pages/assets/ups/tabs/output-load-capacity/UpsCapacityCard.tsx`

- **Primitives mounted**: thin adapter over `ProgressKpiCard` (shell: Card > CardHeader > headline row > progress slot > KPI strips > AiSummary footer) with `headerAction=<StatusPill/>` and `progressContent=<CapacityBar/>` = `FillBar`(h=32, `marker`, `badge`, `fillAboveMarker` two-tone) + `0 / Ready: N / 100` caption row. Loading branch renders `Card`+`CardHeader`+`CardBodySkeleton` directly.
- **Payload → primitive mapping** (`view: UpsCapacityView`):
  - `view.title` → `ProgressKpiCard.title`; `view.status.{label,tone}` → `StatusPill` **directly** (tone is ALREADY the DS `StatusPillTone` — no adapter).
  - Headline: `value: String(view.capacityHeadroom)`, `target: SCORE_MAX` (=100, module constant), `unit: PRESENTATION_LABELS.capacityHeadroom` (='capacity headroom', module constant).
  - `view.capacityHeadroom` → `FillBar.pct`; below-marker → coral, above-marker excess → `fillAboveMarker` sage/600; `view.readyMarkerPct` → marker + caption (caption words `0`, `Ready:`, `100` are HARD-CODED here, unlike 52/54 where they ride the payload).
  - `view.deltaLabel`/`view.deltaTone` → badge; `view.scoreCells: ScoreKpiCell[]` → `kpiStrips=[toKpiStatCells(...)]` with `kpiCellDividers`; `view.insight` → `insight`.
- **Closed vocabularies**: `view.deltaTone` ∈ `'positive'|'negative'|'neutral'` (ternary chain → chip colors); `view.status.tone` ∈ `StatusPillTone = 'normal'|'alarm'|'watch'|'info'` (`STATUS_PILL_TONES` record). Headline denominator/unit and bar captions are constants — payload cannot rebind them.
- **Local state / interactions**: none.
- **Title**: `view.title` verbatim.

### 3.8 UpsLoadCard (card 58)
File: `pages/assets/ups/tabs/output-load-capacity/UpsLoadCard.tsx`

- **Primitives mounted**: `ProgressKpiCard` shell (no headerAction) with `progressContent=<LoadSparkline/>` = inset box > `ResponsiveSvg` > `ChartFrame`(zero margins) > `StackedBars` (30 single-segment teal bars) + start/end caption row.
- **Payload → primitive mapping** (`view: UpsLoadView`):
  - `view.title` → title; headline `value: String(view.averageLoadPct)`, `unit: UNITS.percent` (constant '%'), `unitSuffix: view.averageLoadLabel`, `meta: view.sparklineMaxLabel`.
  - `view.sparkline: LoadSparkPoint[] {label, loadPct}` → bars: `x=(i+0.5)*slot`, `height=yScale(loadPct)` normalized to `max(100, …loadPct)`, fixed color `SERIES_COLOR.loadBar`, `barWidth` clamped 2–6px.
  - `view.sparklineStartLabel`/`sparklineEndLabel` → captions ("-30d"/"now" — payload-carried).
  - `view.scoreCells` → `kpiStrips` (+`kpiCellDividers`); `view.insight` → footer.
- **Closed vocabularies**: bar color + inset surface from tokens; `%` unit constant. Otherwise open.
- **Local state / interactions**: none.
- **Title**: `view.title` verbatim.

## 4. Shared adapter + tone tables (the family's cross-cutting closed vocab)

`pages/assets/ups/shared/adapters.ts`:
- `STATUS_PILL_TONE: Record<'success'|'warning'|'danger', StatusPillTone>` → `normal|watch|alarm`. Used by 50/52/54 (`data.status.tone`, `deltaTone`, `metrics[].tone`). **Unknown tone = record-miss crash class** (`STATUS_PILL_TONES[undefined].bg`).
- `toneChipColors(tone)` — same record, chip `{background:bg, color:fg}`.
- `healthMetricCells(metrics, {withStatus})` — `HealthMetric {label,value,unit?,unitSuffix?,tone,statusLabel}` → `KpiStatCell {id,label,value,unit,unitSuffix,status?}`. `id = label` (labels must be unique per strip).

DS primitive vocab: `StatusPillTone = 'normal'|'alarm'|'watch'|'info'` (`StatusPill.tsx`).

## 5. Generic pres-key dispatch analysis (payload shape → primitive family)

The UPS family reduces to FIVE primitive arrangements. Shape-sniffing keys that can dispatch generically (no card ids):

| Payload signature (keys on the unwrapped inner object) | Primitive family | Cards |
|---|---|---|
| `metrics[] + insight + (soc|score) + (socPct|envelopePct) + barTicks` (+ `readyMarkerPct`, `deltaLabel/deltaTone`) | **progress-KPI card**: CardHeader(+StatusPill) → headline value`/`max → `FillBar`(pct, marker?, badge?) → `KpiStatStrip(healthMetricCells)` → `AiSummary` | 50, 52, 54 (and 57 modulo tone/caption differences — `capacityHeadroom + readyMarkerPct + scoreCells` is the same family through `ProgressKpiCard`) |
| `series[] {key,color,values[]} + zones[] + thresholds[] + yTicks/minY/maxY + xLabels + pointLabels + insight` | **score-history line chart**: ChartFrame + HorizontalBand + GridAxis + ReferenceLine + LinePath×n + InteractiveLegendRow×n + AiSummary | 51, 53 |
| `ticks: boolean[] + tickStartLabel/tickEndLabel + count30d/windowDays + metrics[]` | **event tick strip** (only non-primitive visual in the family — 30 flex spans; portable as a trivial `SegmentBar`/`StackedBars` degenerate or a new 20-line primitive) | 55 |
| `points[] {label,mode,<numeric keys>} + leftAxis + rightAxis + series[] {key,axis} + kpiCells + legend + insight` (g13 sniffs exactly `leftAxis∧rightAxis∧series`) | **dual-axis composite timeline + state strip**: already IS the shared `CompositeChartCard` primitive | 56, 59 |
| `sparkline[] {loadPct} + averageLoadPct + scoreCells + insight` | **bar-sparkline progress-KPI**: ProgressKpiCard + StackedBars | 58 |

Dispatch-key recommendations for a pres vocabulary (mirroring the existing patterns `pres.stackSeries→timeline`, `pres.tiles+tileOrder→tile grid`, `pres.columns+period.panels→table`):
- `pres.fillBar {pct, markerPct?, badge?} + pres.tiles(metrics)` → progress-KPI family (50/52/54/57). The pct/marker/tick captions are already payload fields; only the token colors + the 3-tone maps need a neutral default.
- `pres.scoreSeries + pres.zones/thresholds` → score-history family (51/53). Fully open today — the easiest pure port.
- `pres.eventTicks (boolean[])` → tick-strip family (55).
- `pres.dualAxisSeries + pres.stateStrip(modeKey)` → composite family (56/59) — **blocked by three closed unions**: `series.key ⊂ CompositePoint`, `mode ⊂ UpsMode` (`MODE_COLOR` + hard-coded legend array), `activeView ⊂ CompositeView`. A generic port needs (a) open `points` records with `series.key` as a plain string, (b) a payload-supplied mode palette/legend (`pres.states: [{id,label,color}]`), (c) view options on the payload.
- `pres.sparkBars (values[])` → sparkline family (58).
- Universal leaves already consistent across ALL 10 cards: `title` (in-payload, verbatim — NO titlePrefix/titleConnector/period.label composition anywhere in this family), `insight` → `AiSummary`, `status {label,tone}` → `StatusPill`, `metrics/kpiCells/scoreCells` → `KpiStatStrip` cells.

## 6. Port hazards checklist

1. **Tone record lookups** (50/52/54 `success|warning|danger`; 57 `normal|alarm|watch|info` + `positive|negative|neutral`) — variant tone strings crash or blank; guard with a default tone.
2. **CompositeChartCard closed unions** — `series[].key`, `points[].mode`, `activeView` (§3.6). The state legend is hard-coded to the 3 UPS modes; reuse outside UPS mislabels.
3. **Interaction callbacks on the direct-payload path** — 56/59 `onViewChange`/`onSamplingChange` are undefined (click = TypeError); 51/53 degrade gracefully to a static "Today" chip when `sampling` is omitted.
4. **g13 dependency** — 56/59 only mount because `guards/composite-sampling.ts` injects the required `sampling` value; any refactor must keep the `leftAxis∧rightAxis∧series` sniff or supply `sampling` in the payload.
5. **Bucket-count coupling** — ScoreHistoryCard scales x by `series[0].values.length`; all series must be equal length and `xLabelIndexes`/`pointLabels` must index into it.
6. **57's hard-coded captions** (`0`, `Ready:`, `100`, `/100` target, 'capacity headroom' unit) vs 52/54 where the same captions ride the payload — normalize onto the payload in a port.
