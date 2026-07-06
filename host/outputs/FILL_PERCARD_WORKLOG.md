
## 2026-07-04 — SPLIT panel-overview-real-time-monitoring monolith → sibling folder pattern (PURE refactor)
- Split the last flat monolith `src/cmd/fill/panel-overview-real-time-monitoring.tsx` (308 lines, cards 6/7/8/9/10/11/160 inline) into `src/cmd/fill/panel-overview-real-time-monitoring/` per the feeder-voltage-current / panel-overview-voltage-current idiom.
- Files created (all under host/web/src/cmd/fill/panel-overview-real-time-monitoring/):
  - card-6.tsx (LiveScrubberBar), card-7.tsx (RealTimeMonitoringRail), card-8.tsx (AiSummary), card-9.tsx (SupplyCard), card-10.tsx (TrendCard), card-11.tsx (QuickStats), card-160.tsx (RealTimeMonitoringFooter) — each exports its render fn `cardN`.
  - frame-view-model.ts — socketFromFrame / liveRailVM / footerState + EMPTY_SAMPLE / DEFAULT_RAIL_VM / DEFAULT_HEATMAP_VM / DEFAULT_FOOTER_STATE + noop (live frame → RailViewModel/heatmap/footer derivation via CMD_V2's OWN mapAggregateSocketToSnapshot + buildRailViewModel/buildHeatmapViewModel).
  - payload-unwrap.ts — unwrap(payload,key) + hasSeries/isStatsArray/hasSupply seed guards + the sanitizeSupply NaN-guard (PRESERVED byte-identical; still applied on cards 7 and 9).
  - types.ts — FooterState.
- Flat file reduced to the thin BARREL (32 lines) re-exporting `CARDS = {6,7,8,9,10,11,160}` — the only export registry.tsx consumes (`m.CARDS` via import.meta.glob("./fill/*.tsx"), single-level so the subfolder is not matched). Card 5 stays in cmd/compose.tsx; card 37 intentionally still NOT registered here (feeder page owns it) — both notes preserved in the barrel header.
- Behavior byte-equivalent: no logic changes; honest-degrade precedence per card unchanged (LIVE → seed-with-array-leaf → zero-default VM, never null, never NaN).
- Verify: `npx tsc --noEmit` GREEN; `node -e` barrel sanity → CARDS ids [6,7,8,9,10,11,160] == expected OK.

## 2026-07-04 — VALIDATE fill/feeder-energy-power (cards 39/40/41/42) — page individual-feeder-meter-shell/energy-power
Scope: card-39/40/41/42.tsx + view-model.ts + date-wiring.ts + types.ts + flat barrel feeder-energy-power.tsx. tsc GREEN before and after (no code changes needed — validation found zero defects requiring edits).

Per-card verdicts (all PASS):
- **39 Today's Energy** → TodaysEnergyCard (card_payloads story `…cards--todays-energy` ✓). Props {data, onPeriodChange} match component Props exactly. Every `.toLocaleString()` scalar (activeEnergyKwh/reactiveEnergyKwh/secKwhPerUnit/subsidyLimitKw/energyTargetKwh) is `?? 0`-coerced by CMD_V2's own createEnergyPowerViewModel / createUnavailableEnergyPowerViewModel — no null/NaN can reach formatKwh. periodOptions always an array in both branches.
- **40 Power Energy Analysis** → PowerEnergyAnalysisChart (story `…--power-energy-analysis` ✓). data.bars/demandBars/hourlyAverage/demandBandLegend arrays on all paths; activePowerAvgKw/reactivePowerAvgKw `.toFixed(1)` always finite (0 in empty VM); yMin/yMax via buildChartDomain (empty data → safe 0–100 frame; degenerate ticks loop no-crash).
- **41 Input vs Output** → InputOutputEnergyCard (story `…--input-output-energy` ✓). Component calls .toLocaleString() UNGUARDED on hvInputKw/lvOutputKw/lossKwh/expectedLossKwh/efficiencyPct — inputOutputData() guarantees fully-numeric payload: real HV/LV when mapped, else Input=Output=latest total kW (Layer 2 "total power for both placeholders" note), else all-zero. Zero-defaults only, never seed 475.2/428.2. The literal `?? {…"#000"…}` fallback is an unreachable type-guard (createEnergyPowerViewModel never nulls inputOutput for numeric hv/lv).
- **42 Load Anomalies** → LoadAnomaliesChart (story `…--load-anomalies` ✓). labels/colors meta present in BOTH VM branches (LOAD_ANOMALIES_LABELS/COLORS); actualLoad/expectedLoad/expectedRange/anomalies arrays on all paths; surgeEvents/dipEvents/loadFactorPct/maxThresholdPct numeric.

Guards / swap-safety traces:
- Frame-shape detection (isHistoryFrame buckets/kpis-first, isLiveFrame queue/columns) + try/catch around reducers+mapper: foreign-endpoint frame (aggregate `widgets`, V&C column-rows, undefined) → mapper yields null/'unavailable' → CMD_V2's OWN createUnavailableEnergyPowerViewModel (drawable empty chrome, message as insight). Never crash, never another endpoint's numbers mis-labelled (mapping is by exact ENERGY_POWER_COLUMNS names).
- '—' honest-dash cells: numericColumn/bucketNumeric coerce Number('—')=NaN → null → `?? 0` — a dash can never surface as NaN.
- History frame missing range/start/end/sampling: isHistoryEnvelope rejects → idle socket → honest-empty (no misread).
- Payload is deliberately IGNORED (`payload: _payload`) — no seed unwrap → zero seed-fabrication surface; trivially safe under all-blank payload_stripped skeleton.
- No imports from other page folders (only ./ + @cmd-v2). card_ids 39-42 registered ONLY by this barrel (grep across fill/*.tsx); panel-overview-energy-power barrel comment confirms 40/41 moved here. Barrel = exactly the 4 page_layout_cards rows (680-683) for individual-feeder-meter-shell/energy-power; nothing dead.
- date-wiring periodToDateWindow output matches host DateWindow vocabulary (types.ts mirror OK); CmdCard.onDateChange(dw)→fetchCardFrame contract satisfied.

REPORTED (read-only shared files, not edited):
- registry.tsx renderCmd tries COMPONENTS[id] BEFORE FILL[id], and components.ts maps 39→TodaysEnergyCard, 40→PowerEnergyAnalysisChart, 41→InputOutputEnergyCard, 42→LoadAnomaliesChart — so at runtime these four render via the DIRECT completed-payload path and the FILL fns are dormant last-resort insurance (by design per registry comment: frames now EMPTY; FILL is tier-4). Correct + consistent, just note the fill fns only fire if the COMPONENTS entries are ever removed.

## 2026-07-04 — VALIDATE fill/dg-engine-cooling (cards 60/61/62) — page diesel-generator-asset-dashboard/engine-cooling
Scope: card-60/61/62.tsx + view-model.ts + types.ts + flat barrel dg-engine-cooling.tsx. tsc GREEN before and after. TWO small in-idiom fixes applied.

Per-card verdicts:
- **60 Engine 3D Callout Viewer** → ComingSoon3D (PASS after fix). NO card_payloads row (no Storybook story); page_layout_cards component "ViewerCanvas / ModelLayer" but CMD_V2's own EngineCoolingTab renders <ComingSoon3D label="DG Engine"/> in this slot (3D-kit rebuild pending) — placeholder IS the correct real component. FIX: label derivation now keys off the asset_3d ENVELOPE shape the card actually receives ({object,viewer} → p.object?.label ?? p.title ?? p.label, all null-guarded), matching special.tsx Asset3dEnvelope. NOTE: at runtime SPECIAL[60] (tier-1) renders this card; FILL[60] is the defensive shadow — same pattern as p-o-rtm's card-8 shadowing SPECIAL[8]; kept (in-idiom, not dead-by-design).
- **61 Thermal Timeline** → Panel (EngineHistoryCharts) chart=vm.charts.thermal (story `assets-diesel-generator-engine-cooling-cards--thermal-timeline` ✓, story render = <EngineHoverProvider><Panel vm chart/></> — mirrored exactly). Props {vm, chart} match Panel's destructure; EngineHoverProvider mounted (crosshair context).
- **62 Pressure · Speed · Load** → Panel chart=vm.charts.mech (story `…--pressure-speed-load` ✓). Same contract as 61.

FIX (view-model.ts, both 61+62): on the typed-empty degraded path (no live frame) the CMD_V2 builder's zero-event insight CLAIMED "All temperatures held the expected band…" / "Oil pressure, speed and load tracked normally…" — a fabricated operational statement with ZERO data. Now blanked (`insight: ""` on both charts, live path untouched) — <AiSummary/> renders an empty line; same idiom as dg-operations-runtime / transformer-tap-rtcc degraded view-models.

Guards / honest-blank / swap-safety traces:
- emptyEngineFrame hands buildEngineCoolingViewModel exactly ONE all-zero 'off' point → last=points[0] defined, Math.max over 1 elt finite, detectEvents [] (breach requires runState==='running'), mech avgLoad = round(0/Math.max(1,0)) = 0 — no NaN anywhere; SvgPlot xScale has its own count<=1 branch; buildEngineAxis domains enclose static warn/trip/band references → finite.
- Foreign/undefined frame (swap sim): liveEngineFrame requires Array.isArray(frame.points); a foreign frame with points but no finite `coolant` → trimTrailingNullRows→[] → mapper null; mapper wrapped in try/catch → empty path. Never crash, never another endpoint's numbers.
- Payload deliberately IGNORED by 61/62 (`payload: _payload`) — folder idiom (dg-fuel-efficiency card-65 identical); harvested payload numbers ORIGINATE from the storybook mock fixture (getEngineMockFrame) and engine telemetry has NO neuract source, so ignoring is the fabrication-proof choice. Zeros stay (zero-defaults OK), '—' can never reach a .toFixed (no payload numbers consumed at all).
- No mock imports (getEngineMockFrame/mockSource never imported; only comment mentions). No cross-folder imports (react / ./dg-engine-cooling/* / @cmd-v2 only). card_ids 60/61/62 registered ONLY by this barrel (grep across fill/*.tsx — no duplicates). Barrel = exactly the 3 page_layout_cards rows for diesel-generator-asset-dashboard/engine-cooling; nothing dead.
- No onDateChange wired (EngineDatePicker inside Panel is self-contained, zero-prop; no re-fetchable engine history endpoint) — documented in types.ts, matches registry RenderFn contract (extra args ignored).

REPORTED (read-only shared files, not edited): registry tier order means SPECIAL[60] wins over FILL[60] (defensive shadow, fine); components.ts correctly EXCLUDES 60/61/62 (its own comment: 61/62 need the module-default view-model → FILL tier-4 is their real render path since frames are empty).

## dg-engine-cooling (page diesel-generator-asset-dashboard/engine-cooling) — VALIDATED 2026-07-04, NO FIXES
Cards 60/61/62 (barrel dg-engine-cooling.tsx). tsc --noEmit GREEN. Barrel exports exactly the 3 page cards (page_layout_cards slots 1/2/3), nothing dead. card_ids 60/61/62 globally UNIQUE in FILL (only this barrel defines them).
- card-60 Engine 3D Callout Viewer: NO card_payloads row (envelope card). Normal render = SPECIAL[60] Asset3dEnvelope; card-60.tsx FILL entry is the consistent defensive shadow — both mount CMD V2 <ComingSoon3D label/> (optional-prop, default-safe). Swap-safe: null-guarded label from {object.label|title|label} else "DG Engine".
- card-61 Thermal Timeline: mounts REAL <Panel vm chart=vm.charts.thermal/> (EngineHistoryCharts) via EngineHoverProvider. story assets-...-thermal-timeline == vm.charts.thermal (verified in stories). Props {vm,chart} exact.
- card-62 Pressure·Speed·Load: mounts REAL <Panel vm chart=vm.charts.mech/>. story ...-pressure-speed-load == vm.charts.mech (verified). Props {vm,chart} exact.
- GUARDS/HONEST-BLANK: view-model.ts engineCoolingViewModel(frame) NEVER null. liveEngineFrame requires Array.isArray(frame.points) else null → emptyEngineFrame() hands builder EXACTLY ONE all-zero ZERO_POINT (runState "off"). This is REQUIRED: builder reads points[len-1] (last) + Math.max(...points.map) → empty array would make last=undefined (Number(undefined).toFixed→"NaN") / Math.max([])=-Infinity. One zero point yields honest zeros. buildEngineAxis references (warn/trip/band consts) keep buildChartDomain domain+ticks finite+non-empty. Panel legend/kpis/events all array/scalar-safe on 1 point. No crash, no NaN, no undefined-text.
- NO FABRICATION: zero-event branch insight ("All temperatures held..."/"tracked normally") is BLANKED (insight:"") on the no-live path so no operational claim about absent data; zeros stay as honest typed-empty. getEngineMockFrame NEVER imported/called (only named in forbidden-comments). No mock/demo/sample/fixture fallback objects.
- SWAP-SAFETY: self-contained (imports only ./view-model + @cmd-v2 + react; no other page folder). Unwrap N/A (61/62 ignore payload, key off frame; 60 keys off its OWN {object/title/label}). frame=undefined → typed-empty. frame=<foreign endpoint obj> without .points → typed-empty; with .points of another shape → mapper trims rows lacking finite `coolant` → rows.length 0 → null → typed-empty. Never renders a foreign endpoint's numbers as engine metrics.

## dg-fuel-efficiency (page diesel-generator-asset-dashboard/fuel-efficiency) — VALIDATED 2026-07-04
Cards 63 (FuelTankAnatomy / 3D tank), 64 (RunsList via DataTable), 65 (FuelCompositeCard timeline). All three are
FILL-only (tier 4 last-resort) BY DESIGN — components.ts:91-92 excludes 63/64/65 because they carry NO Storybook
payload and need the module-default view-model. No fixes required; folder is clean and correct.

- COMPONENT: all mount the correct REAL CMD V2 component (cross-checked page_layout_cards 694/695/696 + card_payloads
  63/64/65 import_path FuelEfficiencyCards.stories.tsx). 63=FuelTankAnatomy (dg-overview), 64=RunsList, 65=FuelCompositeCard.
- PROPS: match component destructure exactly. 63 <FuelTankAnatomy snapshot={5-field TankSnapshot} display={vm.tankDisplay}>;
  64 <RunsList runs={FuelRun[]} stats={RunsStats}>; 65 <FuelCompositeCard vm={FuelEfficiencyViewModel}> in <FuelHoverProvider>.
- GUARDS: view-model NEVER returns null. Empty path = emptyFuelFrame() (all-zero snapshot, [] points/runs, ticks=[0],
  labelAt=()=>'') → buildFuelEfficiencyViewModel's defensive empty-`last` branch. snapshot always fully numeric so
  FuelTankAnatomy's .toFixed(0)/levelTone/tempTone never see a non-finite. chart.series/axes = full SERIES/AXES so
  SvgChartBody + buildFuelAxis (band/threshold references) render an empty-but-valid plot. runs always [], runsStats
  always full zero-aggregate.
- HONEST-BLANK: fuel level/rate/temp + run log are DG telemetry neuract does NOT carry → mapper returns null → empty
  view-model → 0% tank / "No runs in this period" / "No fuel data in this window." — real chrome, no crash, no NaN.
- NO FABRICATION: all mock/60%/1626/26.3/107 hits are in COMMENTS (documenting the forbidden pulse); code uses only
  zero-defaults. mockSource is NOT imported. Clean.
- BARREL: fill/dg-fuel-efficiency.tsx exports 63/64/65 (all 3 page cards, nothing dead); globbed via ./fill/*.tsx.
- SWAP-SAFETY: card fns ignore payload (no Storybook seed by design) and key purely off frame→CMD V2 mapper. frame=undefined
  → empty view-model. frame=<foreign endpoint> → mapper trims on 'fuelLevel' key → 0 rows → null → empty view-model
  (try/catch wrapped); no foreign numbers leak. Imports only @cmd-v2/* + own ./view-model. card_ids 63/64/65 globally
  unique (only this barrel exports them; not in COMPONENTS/COMPOSE/SPECIAL). 
- tsc --noEmit GREEN.

## ups-battery-autonomy (cards 50,51,52,53) — VALIDATED 2026-07-04
- DB cross-check: card_payloads 50/51/52/53 all story `assets-ups-battery-autonomy-cards--*`; page_layout_cards page `ups-asset-dashboard/battery-autonomy` serves exactly 50-53. Barrel exports all four, nothing dead.
- COMPONENT: 50→BatteryHealthCard, 51/53→ScoreHistoryCard, 52→BackupReadinessCard — all correct CMD_V2 components; props are the single `data`(VM) prop (+ `sampling` for 51/53). Matches component destructure exactly. No extra/missing props.
- GUARDS: VM built via tab's OWN mapper+viewModel over an adapted envelope; honest-blank path uses EMPTY_FRAME (single 0-bucket survives trimNullRows -> mapper non-null -> viewModel runs full READY branch). Verified no NaN: all .toFixed/Math.round/Math.min/Math.max over non-empty stub arrays -> finite. Normalizer 0-defaults every scalar.
- HONEST-BLANK: blankStubbedProse(ALL_STUBBED) blanks all 4 insight leaves to "—" and drops the peak marker; zero-baseline lines/tiles draw as component's own empty shape. No fabricated measurement prose.
- NO FABRICATION: grep mock/demo/sample/fixture/fake/dummy/seed -> only contract comments; SamplingSelection default is a picker selection, not chart data.
- SWAP-SAFETY: frame=undefined -> null -> typed-empty (ok). frame=<foreign endpoint obj> -> envelope path returns null (no battery block names) AND raw passthrough returns null (foreign frame lacks batteryHistory/autonomyHistory -> trimNullRows empty -> mapper null) -> typed-empty; foreign numbers CANNOT leak. Raw path is STRICT (no stub padding). card_ids 50-53 globally unique (only this barrel exports them). No cross-folder imports (only own folder + @cmd-v2 + shared cmd/).
- tsc --noEmit GREEN. No edits needed — folder already correct and in-idiom.

## feeder-real-time-monitoring (cards 36/37/38) — VALIDATED 2026-07-04, no fixes needed

Page individual-feeder-meter-shell/real-time-monitoring serves cards 36,37,38 (page_layout_cards). Barrel maps all three; globally unique across all FILL barrels (no dup warnings).

- Card 36 PowerEnergyPanel (Cmp19), 37 VoltageMonitorPanel (Cmp20), 38 CurrentMonitorPanel (Cmp21) — match card_payloads import_path + COMPONENTS map. Props {data, freshness} match the panel destructure exactly (READ PowerEnergyPanel/VoltageMonitorPanel/CurrentMonitorPanel + PhaseMonitorPanel + PowerEnergyChart/Rail sources).
- GUARDS: panels only .map over dataSeries/yLabels/series/legendItems/metrics — all guaranteed arrays in ALL 3 fallback tiers (live vm / payload.data seed / createUnavailableRealTimeMonitoringViewModel). No Math.* / toFixed / division on passed scalars in the panels — the view-model pre-formats every reading to a string (displayValue "—" on null). No NaN reachable.
- HONEST-BLANK: payload_stripped.data for 36 (PowerEnergyVM) and 37/38 (PhaseMonitorVM) is fully structured (dataSeries [[],[]] / series[] / metrics[] / legendItems[] all arrays, readings displayValue as real string, freshness complete) → seed tier draws "—" chrome. Terminal unavailable slice also fully structured. NEVER null/NaN/undefined-text.
- NO FABRICATION: zero mock/demo/sample/fixture/fake/dummy in folder. Fallback ladder is live→byte-faithful-seed→CMD_V2 typed-empty (all '—'); no synthetic numbers.
- SWAP-SAFETY: card fns 2-arg self-contained; stateFromFrame shape-guards (queue/.type/.frames) → null on foreign/undefined frame → payload seed. A foreign RTM-shaped frame still yields null readings (numericColumn on absent COL.* returns null, seriesValuesFromQueue returns []) → '—', never another endpoint's numbers. Imports only own folder + @cmd-v2 + shared cmd utils. Unwrap keys off payload.data/.freshness (own shape), not page context. card_id 36/37/38 globally unique.
- NOTE (read-only, not mine to change): 36/37/38 also live in components.ts COMPONENTS, so registry tier-2 (COMPONENTS) wins over tier-4 (FILL) in the normal path — these FILL cards are the swap/last-resort safety net. Correct if invoked.
- tsc --noEmit GREEN. No edits applied.

## feeder-energy-power/ (page: individual-feeder-meter-shell/energy-power) — VALIDATED 2026-07-04

Cards 39/40/41/42; barrel feeder-energy-power.tsx; helpers view-model.ts + date-wiring.ts + types.ts.
DB cross-check: card_payloads 39-42 all -> EnergyPowerCards.stories (todays-energy / power-energy-analysis /
input-output-energy / load-anomalies); page_layout_cards components TodaysEnergyCard / PowerEnergyAnalysisChart /
InputOutputEnergyCard / LoadAnomaliesChart. All 4 match the mounted components. Barrel exports exactly the 4 page cards.

VERDICT: ALL 4 PASS as-is. No fixes needed. tsc --noEmit GREEN (unchanged).

Key evidence:
- Fill drives components from CMD V2's OWN mapper+view-model (createEnergyPowerViewModel /
  createUnavailableEnergyPowerViewModel), NOT the payload seed. energyPowerViewModel(frame) NEVER returns null.
- Components read props PLAINLY (no in-component guards) — safe because the view-model ALWAYS supplies the full
  labelled shape: unavailable branch spreads all *_META, arrays [], scalars 0, valid yMin/yMax. No .map on null, no
  toFixed/toLocaleString on non-finite, no NaN.
- Card 41 (InputOutputEnergyCard calls .toLocaleString() UNGUARDED): inputOutputData(frame) never null — real
  inputOutput when HV/LV metered, else synthesized Input==Output==latest active-power (0-loss/100%-eff honest card via
  the view-model READY branch), else the fully-numeric typed literal fallback. No 475.2/428.2 seed leak.
- HONEST-BLANK: all-blank/absent frame -> drawableEmptyViewModel() -> every card draws its chrome with 0/empty series.
- NO FABRICATION: grep mock/demo/sample/fixture/seed hits are COMMENTS only (describing avoided behaviour). No fake
  numbers on any degraded path. config ?? null -> mapper omits nameplate ref lines (honest-empty).
- SWAP-SAFETY: (a) foreign frame -> liveViewModel try/catch + isLiveFrame/isHistoryFrame gates + assertColumnContract
  only warns (never throws) + reducers coerce queue/columns/buckets to [] and numericColumn->null for missing cols ->
  falls to drawableEmptyViewModel or view-model ?? 0; frame=undefined -> normalizeFrame null -> empty VM. (b) imports
  only @cmd-v2 / react / own ./ folder (verified, zero cross-folder). (c) unwrap keys off own payload (card ignores
  payload, reads frame). (d) card_ids 39-42 GLOBALLY UNIQUE (only in this barrel; panel-overview-energy-power exports
  14-17, confirmed no dup).

## panel-overview-energy-distribution (validated 2026-07-04)

Page `panel-overview-shell/energy-distribution` serves EXACTLY 2 cards (page_layout_cards):
- slot 1 -> card_id 12 EnergyInputDistributionCard ("Energy Input & Distribution")
- slot 2 -> card_id 13 Energy Flow Diagram (component FlowSankey in layout; fill mounts EnergyFlowDiagramCard, story energy-flow-diagram)
Barrel `panel-overview-energy-distribution.tsx` exports {12:card12, 13:card13}. Complete, nothing dead.
card_id 13 has a 3rd card_payloads row (kpi-ribbon-card) but it's NOT a page_layout card and card-13 correctly uses the flow-diagram story shape.

VERDICT: BOTH CARDS PASS as-is. No fixes required.
- COMPONENT ok: card-12 -> EnergyInputDistributionCard, card-13 -> EnergyFlowDiagramCard (both real @cmd-v2 imports, tsc-resolved).
- PROPS ok: 12 passes {vm, selectedNodeId, onToggleNode}; 13 passes {vm, selectedNodeId, onNodeClick} — matches component destructure exactly, no extras.
- GUARDS ok: card-13 StageHeaderRow does Math.max(...vm.sankey.nodes.map(n=>n.layer)); buildEnergyDistributionViewModel UNCONDITIONALLY pushes pcc-panel(layer1)+distribution-allocation(layer2) so sankey.nodes.length>=2 always -> Math.max safe. fmtKwh(number) + safeKwh (non-finite->0) upstream -> no NaN reaches screen. mapper empty-paths return incomingRows:[]/panelRows:[]/mainMeter{0,0}; frame-view-model ??[] guards each.
- HONEST-BLANK ok: fed payload_stripped ({rail:{vm:...}} / {flow:...}) — seed vm is structurally complete with 0.0 values; resolveViewModel adopts it (hasRows+isStructurallyComplete both true) OR falls to liveViewModel(null) structural default. Renders chrome + "0" values, never crash/NaN/undefined.
- NO FABRICATION ok: zero mock/demo/sample/fixture/fake/dummy refs; degraded path = zeroed structural default (honest), never plausible fake numbers.
- SWAP-SAFETY ok: fn fully self-contained. frame=undefined -> resolveViewModel skips live branch -> seed/structural default. frame=<foreign endpoint obj> -> widgetsOf reads only energy-distribution aggregate keys; foreign frame yields empty rows -> hasRows() false -> NOT adopted (never renders another endpoint's numbers). Unwrap keys off OWN payload shape (rail/flow). No cross-folder imports. card_id 12/13 globally UNIQUE (no dup across any barrel; registry uniq -d clean).
- BARREL ok: exports every served card (12,13), nothing dead.

tsc --noEmit GREEN (exit 0), no edits made.

---

## dg-operations-runtime (page diesel-generator-asset-dashboard/operations-runtime) — VALIDATED 2026-07-04

Barrel: src/cmd/fill/dg-operations-runtime.tsx re-exports CARDS {70,71,72,73} — EXACTLY matches
page_layout_cards for the page_key (70 ProgressKpiCard, 71 StackedBars/RuntimeDutyPanel, 72
ProgressKpiCard, 73 PowerEnergyAnalysisPanel). No dead/missing entries. Barrel OK.

Global card_id uniqueness: 70/71/72/73 appear ONLY in this barrel across all fill/*.tsx. No dup.

Self-contained / swap-safe: all imports are react + @cmd-v2/* + ./own-folder ONLY (no cross-folder,
no sibling-page imports). Every card fn IGNORES the payload seed and renders from `frame` via the DG
tab's OWN buildOperationsRuntimeViewModel (view-model.ts) — the strongest no-fabrication form (a seed
number can never leak). FILL is only reached when no COMPONENTS/COMPOSE entry exists for the id.

Guards (verified against CMD_V2 sources):
- opsFrameFrom(frame) ALWAYS returns buckets:[] + a zeroed OpsSnapshot; energy scalars overlaid ONLY
  when numericColumn(row, col) != null (numericColumn coerces "—"/non-finite -> null, never a number).
- isLiveFrame() rejects history frames (f.buckets array) AND any frame lacking queue/columns; reducer
  wrapped in try/catch. frame=undefined AND frame=<foreign endpoint obj> both -> honest-blank.
- LiveOpsCard: service.hours(0).toFixed(0), availability(0).toFixed(1), Math.round(fraction(0)*100),
  ceiling(300 number) — all guaranteed finite. state.label honest-blanked to "—" (StatusBadge takes
  label:string). topKpis/stateKpis all blankCell -> value "—" (rendered as text, no numeric op).
- EnergyReliabilityCard: apparentMvah/pf/activeFraction/reactiveFraction forced to 0 (number) unless
  BOTH energy leaves live -> toFixed/Math.round safe. MTBF/MTTR + per-leaf Active/Reactive honest-blank
  "—". Reliability insight sentence stripped (un-sourced), energy insight only when bothLive.
- RuntimeDutyPanel: duty.points [], duty.topKpis 3-cell array, runs.rows [], runs.columnLabels present
  -> all .map/.reduce/buildChartDomain safe; empty state "No runs in this period" draws.
- PowerEnergyAnalysisPanel: buckets [] -> reduce/filter/map safe; peakDemand.toFixed(0)="0",
  limitKw(1700 number).toLocaleString() safe; selIdx guarded to null when no buckets.

No mock/demo/sample/fixture fallback objects (grep clean — only real CMD_V2 config fn refs).
Card 73 correctly has NO seed (no story_id in card_payloads) — rendered metadata + honest-empty.

tsc --noEmit: GREEN (exit 0). NO EDITS NEEDED — folder already fully in-idiom + correct.

## transformer-tap-rtcc validation ()
- Cards 78/79/80/81 VALIDATED — no edits needed. All four already correct, guarded, honest-blank-safe, swap-safe.
- Architecture: these 4 card_ids are ALSO in components.ts (READ-ONLY, tier-2 COMPONENTS) which is the PRIMARY render path; this FILL folder is the tier-4 last-resort/swap fallback. Not a fixable duplicate (components.ts is read-only) — REPORTED only.
- Guards verified: tapRtccViewModel NEVER returns null; emptyScaffoldFrame keeps regulation[1]+activity[1] non-empty so buildTapRtccViewModel's unguarded now=regulation[last] + peakHour=activity.reduce(...,activity[0]) never throw; buildChartDomain + SegmentedArcGauge fully clamp non-finite/empty. gauge.count=TAP_MAX(5) finite.
- Honest-blank: FILL cards ignore payload, drive off frame only; frame undefined/foreign -> emptyViewModel() draws chrome with points:[] + KPI/legend "—". No NaN, no crash.
- Swap-safety: self-contained; imports only @cmd-v2 + react + own ./ files; foreign frame guarded by toAssetPageFrame(looksLikeFrame) + mapper setpointKv gate -> honest-blank. No mock/demo/fixture fallbacks.
- tsc --noEmit GREEN.

## diesel-generator-voltage-current/ (cards 66,67,68,69) — VALIDATED 2026-07-04
- Page key: diesel-generator-asset-dashboard/voltage-current. DB card_payloads confirms exactly 4 cards
  (66 Voltage Health, 67 Voltage History, 68 Current Health, 69 Current History) — barrel maps all 4, nothing dead.
- COMPONENT: 66/68 mount HealthSummaryPanel, 67/69 mount HistoryPanel (shared electrical panels the DG V&C
  viewModel emits — DgVoltageCurrentCards.stories.tsx args {variant,data}); correct per story_name + component src.
- PROPS: HealthSummaryPanel{data,phaseVariant="bars"} — matches destructure; HistoryPanel{data} — matches. No extras.
- GUARDS: sanitizeHealth finitizes phase widthPct/markerPct (clampPct target) + drops labels-less band; sanitizeHistory
  guarantees EVERY mapped array (stats/legend/events/series/series.values/yTicks/xLabels/xLabelIndexes) + finitizes every
  scaled scalar (minY/maxY/expectedMin/Max/maxLine/minLine) + '—' bucket -> null gap + drops non-finite yTicks (Math.round
  guard). composeValueUnit/KpiStatStrip do pure string interpolation on value (no numeric op) -> '—'/0 never NaN.
- HONEST-BLANK: payload_stripped zeroes numbers + blanks insight (zero-default, allowed); usable() gate -> if metrics/phases
  or series arrays absent falls to CMD V2's OWN createUnavailableVoltageCurrentViewModel slice ('—' scalars, arrays present).
  Never null, never NaN, never crash.
- NO FABRICATION: grep clean — no mock/demo/sample/fixture object with fake numbers; frame.config?.config ?? null so
  nameplate bands honest-omit (no seed). Only "NEVER a mock" comments.
- SWAP-SAFETY: card_ids 66-69 globally unique (only this barrel maps them). liveHealth returns null on a history frame,
  liveHistory returns null on a non-buckets frame -> foreign/undefined frame -> own seed then unavailable slice (never a
  foreign endpoint's numbers). Self-contained: imports only own folder + @cmd-v2 + shared cmd/. Unwrap keys off own payload
  (.data) not page context.
- tsc --noEmit GREEN. NO edits required — folder already fully compliant.

## 2026-07-04 — BATCH-2 PAYLOAD-DIRECT rework: retire dead ems_backend frame path (3 folders)
Scope (owned): feeder-real-time-monitoring (36/37/38), panel-overview-voltage-current (18/19/20/21/22/43), panel-overview-harmonics-pq (23/24/25/26/27). ems_backend RETIRED → host emits frames={} EMPTY, so every `frame` arg is always undefined; the ONLY data source is the Layer-2 `payload`. Retired all dead frame/mapper/reducer branches, render payload directly with guarded honest-blank, deleted now-dead helpers. `npx tsc --noEmit` GREEN.

ARCHITECTURE NOTE (read-only, not mine to change): ALL 14 of these card_ids are also in components.ts COMPONENTS, and registry.tsx tries COMPONENTS (tier 2) BEFORE FILL (tier 4) — so at runtime these render via the DIRECT <Component {...unwrap(payload)}/> path and my FILL fns are the swap/last-resort shadow. The rework still matters: it (a) removes a real FABRICATION path (harmonics buildPQPeriods), (b) deletes dead CMD_V2 frame-machinery imports, (c) keeps the FILL swap-net correct+honest if a COMPONENTS entry is ever removed.

feeder-real-time-monitoring:
- card-36/37/38: deleted the liveViewModel(frame)→reduce→map→createRealTimeMonitoringViewModel branch; render <Panel data={payload.data} freshness={payload.freshness}/>; missing leaf → createUnavailableRealTimeMonitoringViewModel() (CMD_V2's OWN honest-blank slice: empty series, '—', NEVER mock — FE-1). 2-arg → 1-arg (payload only).
- DELETED frame-view-model.ts (dead: mapRealTimeMonitoringSocketToSnapshot + columnRowReducer) and types.ts (RtmSlice — zero consumers). Barrel signature → (payload).

panel-overview-voltage-current:
- view-model.ts: deleted the LIVE aggregate path (panelVcViewModel/liveViewModel/asSnapshotFrame + aggregateFrameReducer + mapPanelVoltageCurrentAggregateToSnapshot imports). KEPT fallbackViewModel() (periods:[] honest-empty, chrome only — buildVcPresentation is labels/colours, NO data) + pure derivations (selectPeriod/statsFor/selectPanelId/bundleFrom/defaultPresentation/hasPanels).
- card-18/19/20/21/22: dropped the panelVcViewModel(frame) tier; render payload → honest-empty fallbackViewModel. card-18 KEEPS its live date control (onDateChange via selectionToWindow — a payload re-fetch, not a frame; date-wiring.ts frame-free, kept).
- card-43: deleted the column-row frame branch (ColumnRowState→mapVoltageCurrentSocketToSnapshot→createVoltageCurrentViewModel + asSnapshotFrame import); render payload.health.data → honestEmptyHealth() (structure-preserving, metrics/phases [], NO source:'mock' seed). 

panel-overview-harmonics-pq (the fabrication fix):
- REMOVED buildPQPeriods() fallback from all 5 cards — it SYNTHESISED iThd/vThd/h3/h5/h7 via Math.sin/cos over panelRows mock fixtures = a SEED/MOCK LEAK. Under retired-frames it would have fired on EVERY payload lacking live periods → fabricated harmonics on data-less panels. GONE.
- DELETED snapshot.ts (dead mapPanelHarmonicsPqAggregateToSnapshot). derive.ts: removed snap-based presentation()/liveTablePeriod(); ADDED honest-empty builders emptyPeriod()/emptyPeriodWithRow()/emptyStats()/blankPanel() (zero counts, '—' chrome, ZERO fabrication).
- card-23/24/25/26/27: render payload periods/stats/period directly; elided → honest-empty. buildHpqPresentation() kept ONLY as chrome fallback (labels/colours/segment+spoke rosters/thresholds — NOT data). card-23 date control kept live.
- CRASH GUARD [card-27]: SignatureCard's MOCK branch reads `selected.h3/h5/…` UNGUARDED; an empty period crashes it. On the no-apiSignature honest-empty path we hand it emptyPeriodWithRow() (ONE blank flat-at-zero row), never a fabricated feeder. The apiSignature branch guards `selected` so a truly-empty period is fine there.

VALIDATION: tsc GREEN. No live refs to any deleted helper/frame-machinery in the 3 folders (grep: only comments). card_ids globally unique per barrel. No cross-folder imports (only ./ + @cmd-v2 + react). NOT curl-verified end-to-end because the FILL path is COMPONENTS-shadowed at runtime (a page render exercises tier-2, not these fns) and /api/run runs a live LLM (times out on a quick curl) — verification is tsc + static fabrication/dead-code audit.
