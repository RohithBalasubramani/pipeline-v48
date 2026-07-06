# COMPLETE_FIXES_WORKLOG

## Frontend batch-1 — panel-overview fill folders retired (2026-07-04)

Lane: PAYLOAD-DIRECT rendering for panel-overview-real-time-monitoring / -energy-distribution / -energy-power.

### Finding (load-bearing)
The registry render precedence (host/web/src/cmd/registry.tsx renderCmd) is:
  SPECIAL[id] → COMPONENTS[id] → COMPOSE[id] → FILL[id]
FILL is the LAST resort. Every card_id in the three fill folders I own is intercepted by a
higher tier that ALREADY does direct payload render `<Component {...unwrap(payload)} />`
(from the READ-ONLY components.ts / compose.tsx / special.tsx):
  - 7,9,10,11,12,13,14,15,16,17  → COMPONENTS[id]  (real CMD_V2 component, direct payload)
  - 6,160                        → COMPOSE[id]     (RTM LiveScrubberBar / RealTimeMonitoringFooter chrome)
  - 8                            → SPECIAL[id]     (narrative_ai envelope)
So the FILL barrels + folders registered ONLY unreachable dead code. Their bodies were the
retired ems_backend frame path: liveRailVM(frame) / footerState(frame) / resolveViewModel(frame)
/ resolveView(...,frame) / mapAggregateSocketToSnapshot wrappers — all reading the now-EMPTY
`frame`. Since frames={} and every id is served by a higher tier, none of it can ever execute.

### Verification the higher tiers render these correctly
- card_payloads import_path/story_id cross-checked → matches the COMPONENTS mapping
  (7=RealTimeMonitoringRail, 9/10/11=RealTimeMonitoringRailCards Supply/Trend/QuickStats,
   12=EnergyInputDistributionCard, 13=EnergyFlowDiagramCard, 14/15=EnergyProgressCard,
   16=EnergyTrendCard, 17=DemandProfileCard).
- CMD_V2 component prop signatures cross-checked vs registry unwrap() aliasing:
  RealTimeMonitoringRail reads `railVM` (own-key), EnergyInput/FlowDiagram read `vm`,
  EnergyProgress/Trend/Demand read `view` — unwrap() supplies inner under own-key + data/vm/view
  aliases, so every prop shape is satisfied.
- 6/8/160 have no card_payloads row (chrome / narrative) → COMPOSE/SPECIAL draw their own
  defaults / envelope. Honest-blank preserved (empty history → empty axis + static legend; no seed).

### Action
DELETED (dead, unreachable):
  host/web/src/cmd/fill/panel-overview-real-time-monitoring.tsx  (barrel)
  host/web/src/cmd/fill/panel-overview-real-time-monitoring/     (card-6/7/8/9/10/11/160 + frame-view-model.ts + payload-unwrap.ts + types.ts)
  host/web/src/cmd/fill/panel-overview-energy-distribution.tsx   (barrel)
  host/web/src/cmd/fill/panel-overview-energy-distribution/      (card-12/13 + frame-view-model.ts)
  host/web/src/cmd/fill/panel-overview-energy-power.tsx          (barrel)
  host/web/src/cmd/fill/panel-overview-energy-power/             (card-14/15/16/17 + viewModel.ts + dateWiring.ts + placeholder.tsx + types.ts)

No external importers (only the barrels imported their own folder files; two sibling references
were COMMENTS not imports — feeder-voltage-current/payload-unwrap.ts, harmonics-pq/snapshot.ts).
registeredCardIds() still includes all 13 ids via the higher tiers.

### Validation
`cd host/web && npx tsc --noEmit` → EXIT 0 (GREEN), same as pre-change baseline.
(A /api/run curl for "PCC Panel 1 real-time monitoring" timed out at 120s = backend/LLM latency,
 unrelated to this pure-frontend dead-code removal.)

---
## FRONTEND batch-5 — payload-direct rendering (ems_backend retired) — 2026-07-04

Folders (owned): diesel-generator-voltage-current (66-69), transformer-tap-rtcc (78-81), transformer-thermal-life (74-77).
ems_backend is RETIRED (host emits frames={}), so `frame` is ALWAYS empty. Retired every dead frame/mapper/socket path
and render the Layer-2 `payload` DIRECTLY as each CMD V2 component's props (payload IS the render source).

- transformer-tap-rtcc/view-model.ts REWRITTEN: deleted toAssetPageFrame/liveViewModel/blankActivity/mapTapRtccToFrame
  frame machinery. New per-slice accessors tapPositionVM/tapChangesVM/regulationVM/activityVM read payload.<slice> (story
  args `{variant,<slice>:VM}`), merge over the tab's OWN empty-vm (buildTapRtccViewModel over a scaffold), finitize every
  chart-math scalar (gauge value, axis min/max, point voltageKv/count) so a '—' never renders NaN geometry. cards 78-81
  render <Card vm={…VM(payload)}/>, dead `frame` param dropped (79/81 keep onRequest→onDateChange date-nav).
- transformer-thermal-life/view-model.ts REWRITTEN: deleted reshapeFrame/variantOf/widgets frame-envelope machinery. New
  thermalLifeVM/lifeCapacityVM/timelineVM/agingVM read payload.<slice>, merge over the empty-vm (buildThermalLifeViewModel
  over a single-'—'-bucket scaffold — the component indexes points[len-1] + .toFixed on every scalar). CRITICAL guard:
  lifeRemainingYears/stress/FillBar pcts/point scalars finitized (`lifeRemainingYears.toFixed(1)` throws on null/'—').
  cards 74-77 render payload-direct, dead `frame` dropped (76/77 keep onRequest date-nav).
- diesel-generator-voltage-current: DELETED frame-view-model.ts (mapper+columnRow/history socket reducers+viewModelFromFrame
  +liveHealth/liveHistory). Added empty-view-model.ts = just createUnavailableVoltageCurrentViewModel honest-blank slices.
  cards 66/68 (HealthSummaryPanel data=payload.data phaseVariant=bars) + 67/69 (HistoryPanel data=payload.data) render
  payload-direct via the KEPT payload-unwrap.ts (healthData/historyData/sanitizeHealth/sanitizeHistory guards). Removed dead
  `Slot` type from types.ts.

No-seed: payloads are honest-blanked SERVER-SIDE (strip_to_placeholders scalar=None); a '—'/null in a chart-math leaf is
finitized to 0 / dropped so it draws chrome+dashes, never a Storybook seed number and never NaN. Swap-safe: each card
renders from payload alone, globally-unique card_id, no sibling-folder imports. `npx tsc --noEmit` GREEN for all 3 folders
(2 remaining repo errors are in dg-engine-cooling — another agent's untracked lane, not mine).

## Frontend batch 6 — UPS fill folders RETIRED (payload-direct render) — 2026-07-04

Lane: ups-battery-autonomy (50/51/52/53), ups-source-transfer (54/55/56), ups-output-load-capacity (57/58/59).

FINDING: all 9 card_ids are ALREADY in the READ-ONLY components.ts COMPONENTS map and render via the
PRIMARY direct path `<Comp {...unwrap(payload)} />` in registry.tsx (checked BEFORE FILL). The three FILL
folders + their 3 barrels were 100% DEAD CODE: each card fn ignored `payload` and derived its VM from the
now-always-EMPTY `frame` (ems_backend retired) → always the typed-empty view-model. The whole frame/mapper
path (envelopeToAssetFrame, mapUps*ToFrame, buildUps*ViewModel over stub frames, date-wiring) was unreachable.

ACTION: DELETED the dead frame path entirely (untracked files, never committed):
  - fill/ups-battery-autonomy.tsx  + folder (card-50..53, view-model.ts, date-wiring.ts, types.ts)
  - fill/ups-source-transfer.tsx   + folder (card-54..56, view-model.ts, date-wiring.ts, types.ts)
  - fill/ups-output-load-capacity.tsx + folder (card-57..59, view-model.ts, date-wiring.ts, types.ts)
Removed barrel + folder ATOMICALLY so import.meta.glob has no dangling import (unlike the concurrent
dg-operations-runtime lane which left a barrel importing deleted card files).

VALIDATION (curl /api/run asset_id=11, all three UPS pages resolved, cards render from payload alone):
  - 50 {variant,batteryHealth} 51 {variant,batteryHistory} 52 {variant,backupReadiness} 53 {variant,backupHistory}
  - 54 {variant,readiness} 55 {variant,activity} 56 {variant,composite}
  - 57 {variant,capacity} 58 {variant,load} 59 {variant,composite}
  unwrap() aliases the single inner object → the component's data/vm/view prop. NO SEED survived: card 50
  soc 92→0.0, insight blanked ""; card 57 scoreCells values all "—", insight "", capacityHeadroom null.
  Real electrical proxies filled (card 50 Output Voltage 236.4V / Current 279A).
GUARD: honest-blank payload is TYPE-PRESERVING (nested status/barTicks/metrics/scoreCells objects+arrays kept,
only scalars→null/'—'), so direct render draws chrome+dashes, never NaN/crash (FillBar clampPct(null)→0%).

tsc: my three lanes = ZERO errors (grep clean). The 20+ tsc errors present are ALL in OTHER agents' lanes
(dg-operations-runtime, feeder-energy-power, panel-overview-harmonics-pq, panel-overview-voltage-current),
modified 18:11–18:17 today mid-refactor — not caused by this lane (baseline at session start was exit 0).

BACKEND/F2 NOTE (not my lane, host serve boundary): card 57 `capacityHeadroom` is served as raw `null`
(not dashed to '—' like scoreCells), so UpsCapacityCard renders `String(null)`="null" as the headline text
and FillBar coerces null→0%. host/display_dash.py should dash capacityHeadroom (unit-adjacent scalar) too.

═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
F4 — DERIVABLE ENERGY (∫power dead-counter recovery)   [BACKEND lane — derivations]   2026-07-04
═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
SYMPTOM: 'Energy consumption of Transformer-05 today' (energy pages generally) honest-blanked. Confirmed on live
neuract: gic_24_n3_pcc_03_transformer_05_se logs active_power_total_kw = -456.75 (reversed-CT) continuously, but the
4 energy-counter registers (active/reactive import/export kWh) are all-NULL → every windowed-delta energy derivation
returned None. kWh IS derivable: energy = ∫P dt.

FIX (generic, DB-driven, per-leaf honest, zero fabrication):
 1. ems_exec/derivations/energy.py — NEW pure fns:
      energy_from_power_kwh(ctx[,power_col])   — trapezoidal ∫|power| dt over ctx['series'] (reversed-CT abs);
                                                 honest-degrade None on <2 usable samples / no positive elapsed time.
      reactive_energy_from_power_kvarh(ctx)    — reactive twin.
      _dt_hours()                              — datetime|ISO elapsed-hours helper.
    DEAD-COUNTER FALLBACK wired into the EXISTING windowed-delta fns (no new AI vocab needed): window_energy_kwh,
    todays_energy_total_kwh, active_energy_today/this_week/this_month_kwh now call energy_from_power_kwh(ctx) when
    their cumulative-counter / period-delta path yields None. Live counter still PREFERRED (real_exact).
 2. ems_exec/data/neuract.py — NEW series(table, cols, start, end, sampling) reader: down-sampled (date_trunc AVG),
    NULL-skipping, spans the WHOLE window (fixes the raw-LIMIT truncation-to-window-start bug — power is NULL early in
    the day on this meter). Drops fully-dead buckets so ∫ never straddles a gap. Rows carry ts (datetime).
 3. ems_exec/executor/fill.py — _run_derived now builds ctx['series'] for window/series-scoped fns (binding.scope in
    {series,window}) = the windowed series of frame cols PLUS _INTEGRATION_POWER_COLS (active/reactive power) so the
    ∫-fallback has its integrand. HONEST FIDELITY: a real_exact energy metric whose counter cols are ALL absent at both
    window endpoints yet produced a value → downgraded to real_approx ('integrated from power'). A live-counter meter
    (dg_1_mfm) stays real_exact — verified no false downgrade.
 4. ems_exec/derivations/registry.py — LIBRARY += energyFromPowerKwh / reactiveEnergyFromPowerKvarh
    (recover_class integrated_from_power). _execute() EXPRESSION-DEGRADE FALL-THROUGH: a derivation_binding.expression
    that honest-degrades to None (e.g. windowEnergyKwh's counter-delta expr on dead counters) now falls through to the
    retained python fn (which recovers via ∫power) instead of returning None. Expression still WINS when it yields a
    number (authoritative happy path).
 5. config/derivation_binding.py — binding() now also returns `scope` (default 'row').
 6. cmd_catalog.derivation_binding rows: activeEnergyToday/ThisWeek/ThisMonthKwh scope row→series; INSERTED
    energyFromPowerKwh + reactiveEnergyFromPowerKvarh (real_approx, series, base = power col + ts).

VERIFY (non-live unit + ONE targeted run_card):
 - tests/test_energy_from_power.py — 18 pass (trapezoid, reversed-CT abs, ISO ts, honest-degrade, live-counter-prefer,
   period-delta fallback, registry expression-degrade fall-through, neuract series NULL-bucket drop).
 - tests/test_derivation_evaluate.py — 27 pass (no regression from the _execute fall-through change).
 - run_card(Transformer-05, activeEnergyTodayKwh, today) → todayKwh = ~3084 kWh (was None), no gap. real_approx.
 - dg_1_mfm (live counter) windowEnergyKwh stays real_exact — fidelity downgrade does NOT false-fire.

---
## FRONTEND batch-4 — PAYLOAD-DIRECT migration of DG asset fill folders (2026-07-04)

Owner lane: dg-engine-cooling, dg-fuel-efficiency, dg-operations-runtime (host/web/src/cmd/fill/).
Directive: ems_backend RETIRED (host emits frames={} EMPTY) → payload is the ONLY data source. Retire dead
frame/mapper/assetPageSocket paths; render Layer-2 payload DIRECTLY as CMD_V2 props with honest-blank guards.

### Per card
- 60 (Engine 3D Callout Viewer): DEAD FILL shadow — SPECIAL[60] Asset3dEnvelope (ComingSoon3D) wins in renderCmd
  BEFORE FILL. Deleted card-60.tsx + removed 60 from dg-engine-cooling barrel. (declined/dead)
- 61 Thermal Timeline / 62 Pressure·Speed·Load: payload {chart}. Panel({vm,chart}) needs vm.points for the plotted
  series — engine telemetry has NO neuract column, so Layer-2 carries no points. engineCoolingViewModel(payload,
  chartId) builds CMD_V2's OWN typed-empty vm (1 all-zero point → valid axes/band/legend/KPIs, empty series) and
  OVERLAYS the payload's real `chart` chrome (title/kpis/legend/insight, real or '—') onto vm.charts[chartId].
  Deleted the liveEngineFrame/mapDgEngineCoolingToFrame/assetPageSocket path.
- 63 Fuel Tank Anatomy: payload {snapshot, display} → FuelTankAnatomy({snapshot,display}) DIRECT. tankSnapshot()
  finitizes every field (honest-blank '—' → 0) so .toFixed()/3D fill never NaN — empty (0%) tank on blank.
- 64 All Runs (Fuel Log): payload {stats} → RunsList({runs:[], stats}). Run log has no neuract source → runs always
  []; RunsList draws its own "No runs in this period" under the real header. No seed 36-starts/1626 L.
- 65 Fuel Composite: payload {chart} → FuelCompositeCard({vm}); same overlay pattern as 61/62 (points empty).
- 70 Live Ops / 72 Energy&Reliability: DEAD FILL — COMPONENTS Cmp70/Cmp72 win BEFORE FILL (payload {liveOps}/
  {energyReliability} → unwrap aliases to `view`). Deleted card-70.tsx + card-72.tsx + removed from barrel. The
  old per-leaf MTBF/MTTR blanking now belongs to Layer-2 (server-side), not the FE.
- 71 Runtime & Duty: payload {duty} → RuntimeDutyPanel({duty, runs:emptyRunsView, sampling…}). dutyView() prefers
  the payload duty slice over CMD_V2's empty DutyView; runsView() is CMD_V2's OWN empty RunsView. SamplingPicker +
  onDateChange kept (re-fetch is a no-op now, control is real chrome).
- 73 Power Energy Analysis: NO payload → PowerEnergyAnalysisPanel({buckets:[], limitKw:DEMAND_LIMIT_KW=1700,…}).
  Metadata-only: empty buckets (no run-hours-derived source) + demand-limit nameplate line for the axis.

### Deletions
- host/web/src/cmd/fill/dg-engine-cooling/card-60.tsx (dead — SPECIAL wins)
- host/web/src/cmd/fill/dg-engine-cooling/types.ts (dead DateWindow/OnDateChange — no onDateChange wired)
- host/web/src/cmd/fill/dg-fuel-efficiency/types.ts (dead — no onDateChange wired)
- host/web/src/cmd/fill/dg-operations-runtime/card-70.tsx + card-72.tsx (dead — COMPONENTS wins)
- date-wiring.ts::onSamplingChange() (unused helper; only samplingToWindow is imported)
- All liveXxxFrame / mapDg*ToFrame / assetPageSocket / columnRowReducer / ENERGY_POWER_COLUMNS logic in the 3 view-models.

### Validation
- Scoped tsconfig over ONLY my 3 folders: `npx tsc --noEmit` → EXIT 0 (GREEN, incl. all CMD_V2 imports).
- Full `npx vite build` → EXIT 0 (4024 modules transformed) — proves all imports resolve, no dangling refs.
- Project-wide `npx tsc --noEmit`: the ONLY remaining errors are in panel-overview-harmonics-pq/ (another agent's
  in-progress lane, deleted snapshot.ts / changed derive.ts) — NONE in my folders. Not blocked by my code.
- Swap-safe: no cross-folder sibling imports; all card_ids globally unique across fill barrels.

## Frontend batch 3 — PAYLOAD-DIRECT rewrite of 3 feeder fill folders (frames retired)

Scope: host/web/src/cmd/fill/{feeder-voltage-current, feeder-energy-power, feeder-power-quality}. Retired the dead ems_backend frame/mapper/reducer/socket path (host emits frames={} EMPTY — the `frame` arg is always undefined). Every card now renders its REAL CMD V2 component DIRECTLY from the Layer-2 payload, guarded.

Key finding: all 11 cards (39/40/41/42/44/45/46/47/48/49) ARE in the READ-ONLY COMPONENTS map, which renderCmd checks (tier 2) BEFORE FILL (tier 4). But `unwrap()` mis-shapes the NESTED payloads: cards 44/46 (`{history:{data}}`), 45 (`{health:{data,phaseVariant}}`), 48/49 (`{distortionProfile|loadImpact}` + missing sampling chrome) do NOT render correctly via raw COMPONENTS+unwrap — the fill path is the CORRECT renderer for those. Cards 39/40/41/42/47 render fine via COMPONENTS but their fill fns now match. Verified all 10 canonical card_payloads shapes against each card fn's extractor (100% PASS).

Per-card:
- 44/46 VoltageHistory/CurrentHistory: read payload.history.data → sanitizeHistory (series bucket '—'/null → line gap, yTicks/refLines finite-or-dropped) → HistoryPanel + withDateControl. Honest-blank → CMD V2's createUnavailableVoltageCurrentViewModel slice.
- 45 CurrentHealth: read payload.health.data + payload.health.phaseVariant → sanitizeHealth (phase widthPct/markerPct '—' → 0, never NaN width%; '—' text VALUES preserved) → HealthSummaryPanel.
- 39/40/42 energy: read payload.data → todaysEnergy/powerAnalysis/loadAnomalies; honest-blank → createUnavailableEnergyPowerViewModel slice (empty series, valid axis, full chrome).
- 41 InputOutput: InputOutputEnergyCard reads 5 numerics UNGUARDED (.toLocaleString) — force finite (honest-blank → 0) keeping labels/colours byte-identical; absent-slice fallback = zeroInputOutput() built via createEnergyPowerViewModel READY branch (createUnavailable sets inputOutput=null → would crash).
- 47 PowerQuality: read payload.snapshot → sanitizeSnapshot against typed placeholder (spectrum/VQ leaves stay guarded object-shape).
- 48/49 Distortion/LoadImpact: read payload.distortionProfile|loadImpact → hasUsable* structural gate (all views array-safe) else createPowerQualityViewModel(nullLimitBase) empty slice; inject SAMPLING + POWER_QUALITY_SAMPLING_PRESETS + SAMPLING_RESOLUTION_OPTIONS chrome; onDateChange threaded.

Deletions (dead frame code): feeder-voltage-current/frame-view-model.ts, feeder-power-quality/mappers.ts, feeder-power-quality/guards.ts, feeder-voltage-current/types.ts::Slot type.

No-seed / no-NaN: server-side display_dash + forceBlank blank unprovenanced leaves BEFORE the payload reaches these cards; the FE sanitizers convert any non-finite/'—'/null data leaf to the component's own blank shape (line gap / 0 width% / '—' text) — proven by guard simulation. No Storybook seed number survives into a data leaf (the card reads the payload's slice, which is already honest-blanked). Swap-safe: no cross-sibling-folder imports; each card renders from payload alone.

Verify: `cd host/web && npx tsc --noEmit` GREEN (0 errors). card_payloads shape-match harness PASS 10/10. Guard-logic simulation PASS (card41 numerics→0 never NaN + labels kept; card44/46 buckets→null gap; card45 pct→0 + '—' preserved). NOTE: individual-feeder-meter-shell/* pages currently emit 0 cards from /api/run (backend card-emission gap on feeder pages — NOT this frontend lane), so no live curl could exercise these renders end-to-end; validated against harvested payload shapes instead.

## 2026-07-04 — BACKEND LANE (fill + reason channel): F2 / F3 / F7 / F8

Owner scope: ems_exec/executor/* + ems_exec/data/neuract.py + host/server.py per-leaf stats/reason. Did NOT touch layer1b/, layer2/emit, host/web.

### F2 (HIGH, fabrication) — displayValue SEED-LEAK fixed
- NEW ems_exec/executor/display.py — DISPLAY-SIBLING RECONCILE. Generic, shape-driven (value/display keys from config.vocab element_value_keys + closed code default; no card ids).
  - GLOBAL invariant: displayValue ≡ fmtMetric(value) = value.toFixed(decimals) | '—' for EVERY {value, displayValue} object. Can only make the string consistent with its value; never introduces a seed.
  - WRITTEN-scope: for each leaf the executor actually wrote (fill tracks written_value_paths), blank the un-recomputable %-change/rate projections (delta / deltaText.value / *DeltaPerMinute) so no Storybook delta renders beside a live/blank value.
- fill.py: track `written_value_paths`; call display.apply(out, written_value_paths) as the LAST fill pass (after roster + yscale).
- Live end-to-end proof (dg_2_mfm, real neuract): seed displayValue '325.9'/'338.8'/'92.6' → '0.0' (real idle DG value); undeclared readings stay internally consistent.
- Test: tests/test_fill_display_siblings.py (9).

### F7 (leaf-reason-contradicts-DB) — never claim a live column is unlogged
- neuract.py: NEW column_logged(table, col) — cached 'any non-null?' read.
- fill.py _gap_of: a present + LOGGED column that blanked → denorm_garbage (NOT structurally_null 'not logged'); only a genuinely 100%-NULL present column reads structurally_null. Same fix for derived base columns. Root cause was trusting the incomplete latest_row cache (bucketed/event cols not preloaded → mislabeled live cols as unlogged).
- Verified on the exact live-failing column active_power_total_kw (dg_2_mfm, 100% non-null, all-zero): now denorm_garbage across raw/bucketed/event; a real NULL column (kpi_true_pf) still reads structurally_null.
- Test: tests/test_fill_reason_not_logged.py (5).

### F3 (per-leaf reason, never whole-asset when the asset has data)
- host/server.py: NEW _asset_has_logged_data(asset_table) + _per_metric_blank_reason(di, asset_name). _enrich_card now takes asset_table; when n_real==0 and no per-leaf gap sentence survived, the whole-asset 'No data logged for this asset' reason fires ONLY if the meter is genuinely dark — else a PER-METRIC 'X, Y not logged by this meter' reason naming the dead declared metrics. (When executor gaps exist, gap_note already wins — this is the no-gap fallback.)
- Test: tests/test_enrich_reason_per_leaf.py (2).

### F8 (blind leaves) — verdict now verifies series/roster/object slots
- host/server.py _card_leaf_stats rewritten: resolve each DECLARED slot and classify its subtree — scalar → 1 leaf; array → its elements (empty → 1 honest-blank); reading OBJECT → only its value-key leaves (chrome ignored). Previously only a scalar leaf whose path == a declared slot counted, so a filled history series scored 0/0/0 and judged render/full with nothing verified.
- Live curl (stale host) reproduced the defect: card 73 leaf_stats 0/0/0 verdict=render (BLIND) and card 70 reason 'active_power_total_kw not logged by this meter' (F7). Edited code eliminates both.
- Test: tests/test_card_leaf_stats_blind_leaves.py (8).

Regression: 84 executor/host/reason/column tests pass. Sole failing test (test_available_pages) is a LIVE :8200 LLM test failing on a transient empty-response outage — unrelated to these changes. Running host :8770 NOT restarted (not the Gate agent); AFTER-fix proven via unit tests + in-process live-executor run on real neuract.

---
## 2026-07-04 — BACKEND LANE (asset resolution): F5/F6/P03/P08/P09/P10 name-collision discipline

ROOT CAUSE (all six): the confident-pin path had two wrong behaviors when a prompt named a class+unit token
(DG-03, UPS-04, UPS-01, Transformer-03, UPS-10) that maps to MULTIPLE distinct registry assets:
 1. it confidently pinned ONE (often the wrong physical asset), and
 2. the DS-09 `_TWIN_FAMILIES` rule in confident_pin.py merged `dg_N_mfm` with `gic_28_nN_dg_0N_jk` as "one genset
    logged twice" and silently re-pointed the pin — which is FALSE: the canonical registry_device_mappings prove every
    physical device has its OWN device_id ('DG-3 MFM'=dev_...904 vs 'GIC-28-N3-DG-03 [Jackson]'=dev_...031), and NO
    device_id spans two tables. So the "twin" merge collapsed genuinely-distinct homonyms → mis-pin (F5) + dropped the
    correct row from the picker (F6).

FIX (all on the canonical mirror; AI-first, generic, no hardcoded names):
 - NEW layer1b/resolve/name_collision.py — deterministic, prompt-driven:
     · unit_tokens(text): (class-word, unit-int) tokens via the DB-driven class vocabulary (class_concept_hints).
     · colliding_rows(prompt,cands): all RENDERABLE registry rows sharing any prompt token (ghosts excluded).
     · uniquely_named(prompt,rows): a prompt that spells one row out in FULL (whole name OR unique GIC-node prefix
       'gic-NN-nM') pins it — so 'GIC-01-N3-UPS-01' still confidently resolves (reconcile path preserved).
     · is_collision: >1 distinct RENDERABLE row (by canonical id, no twin merge) AND not uniquely named → picker.
 - asset_resolve.py: collision gate lifted ABOVE every AI-driven branch. Colliding token → asset_pending + the
   registry-wide colliding candidate set (fixes F6 recall: the correct-named asset is always present, wrong-unit rows
   never leak). Ghost-pin guard: a confident pick with table_exists=False (P03 `_sch` ghost) is never pinned.
 - confident_pin.py: REMOVED the false DS-09 twin de-dup (_TWIN_FAMILIES/prefer_populated deleted). _ident/
   device_identity kept as a no-op seam (return None) — each registry row is its own device. dedup in
   ambiguous_candidates.py degrades to pure registry-id de-dup (comment corrected).
 - asset_candidates.py: row shape extended with table_exists at index 9 (+as_asset key) — the GHOST flag the
   collision/ghost-guard read (14 canonical rows point at tables neuract never created).

PER-FIX (verified by unit tests + resolve_asset() over the exact prompt, LLM live):
 - F5  DG-03 Jackson  → asset_pending, candidates [4 'DG-3 MFM', 302 'GIC-28-N3-DG-03 [Jackson]'] (no confident mis-pin).
 - F5/P10 UPS-04      → asset_pending, candidates [191,299,23] (the 3 real UPS-04s; Laminator-4.1 id 156 excluded).
 - F6/P08 UPS-01      → asset_pending, candidates [11,188,192,194,296] — INCLUDES GIC-01-N3-UPS-01 (id 11), EXCLUDES UPS-07 (233).
 - P03 Transformer-03 → asset_pending (was asset→None/no_data); ghost id 167 (_sch, table_exists=F) dropped; real 173 (_se) + 100176 (pqm) offered.
 - P09 UPS-10         → asset_pending, candidates [78 'UPS - 10', 236 'UPS-10 Incomer-4']; the correct UPS-10 (id 78, spaced form) present. Card-45 payload_error was a downstream (layer2/emit) effect of confidently pinning a single asset — no confident pin now → not triggered; the emit-side error is out of this lane.
 - Full name 'GIC-01-N3-UPS-01' → still confidently pins id 11 (reconcile test green).

TESTS: tests/test_layer1b_name_collision.py (13, non-live, deterministic over the mirror) all pass; existing
tests/test_layer1b_asset_resolve.py (7), test_layer1b_column_basket.py (4), test_layer1_reconcile_no_data.py (12) all
still green. No importers of the removed prefer_populated/_TWIN_FAMILIES outside confident_pin.

---
## 2026-07-04 — FINAL GATE (offline + targeted per-fix confirm; Gate agent)

### Offline gate
- pytest `-m 'not live' -q`: **248 passed, 14 skipped, 40 deselected, 0 failed** (273.8s). GREEN. No cross-lane breakage.
- `npx tsc --noEmit` (host/web): **0 errors**. Clean.
- Registry/renderer coverage — the 18 routable pages (cmd_catalog.routable_pages, matches config/available_pages code-default exactly: 5 panel-overview + 4 feeder + 9 asset):
  · 70 distinct card_ids across the 18 pages → **all 70 resolve** to a render tier (SPECIAL 8/28/60 · COMPONENTS 54 ids · COMPOSE 5/6/160 · FILL 43 ids). UNCOVERED = [] .
  · fill-ONLY (last-resort) ids = [61,62,63,64,65,71,73] — the documented no-Storybook-payload DG cards. Expected.
  · No duplicate card_id across fill folders (registry.tsx glob + `uniq -d` both clean).
  · No card-N.tsx imports a sibling fill folder (grep = 0).

### Service restart
- STALE-PROCESS GOTCHA (found + fixed): :8770 was being served by an OLD pyenv host (pid 3750492, started 17:44 — BEFORE the 18:58 name_collision.py fix), so the FIRST P03 curl reproduced the pre-fix crash (confident-pinned the `_sch` ghost → `RuntimeError relation neuract.gic_15_n12_pcc_02_transformer_03_sch does not exist`). The in-process `run_pipeline` returned the CORRECT ambiguous outcome, proving the fix code was right and only the running process was stale. My first restart failed to bind (port still held by the stale proc, which a racing `fuser` had missed). Killed pid 3750492 directly, cleared host/layer1b/run __pycache__, relaunched. Fresh host (started 19:35, pyenv 3.11.9) now binds :8770.
- host :8770 `/api/health` → {ok:true}; vite :5188 → 200. Both healthy.
- (Root cause is a latent robustness gap, not re-fixed in this gate lane per scope: col_dict.latest_nonnull() issues an UNGUARDED `to_jsonb(t) FROM neuract."{table}" LIMIT 1` — a ghost/missing table there raises instead of degrading. It is only reachable when an asset is confidently pinned, so the collision/ghost-guard fix keeps it off the ghost path; flagged for the layer1b lane.)

### Targeted per-fix confirm (one curl each, fresh host)
| id | prompt | result | status |
|----|--------|--------|--------|
| P03 | Show voltage levels for Transformer-03 | asset_pending=T, how=ambiguous, candidates=[173 'GIC-15-N5-PCC-02 (Transformer-03) [Secure Elite300]', 100176 'PQM Transformer-3 Incomer'] — ghost 167 dropped, no errors | PASS |
| P08 | UPS-01 load percentage right now | asset_pending=T, 5 candidates INCLUDING GIC-01-N3-UPS-01 (id 11), EXCLUDING UPS-07; no errors | PASS |
| P09 | Show voltage for UPS-10 | asset_pending=T, candidates=[78 'GIC-07-N5-UPS - 10', 236 'UPS-10 Incomer-4']; 0 cards → NO payload_error; no errors | PASS |
| F2 | Real-time monitoring for GIC-01-N3-UPS-01 (confident pin → feeder RTM, 3 cards) | 6 {value,displayValue} leaves scanned across all rendered cards → 0 mismatches (dv==fmt(value) or dash; no seed beside blank; no real value beside stale dv) | PASS |

### LOC delta (working tree, cumulative across all fix lanes)
- Whole pipeline_v48 tree: 472 files, +4985 / −33252 (net −28267 — dominated by dead fill fn / frame-path removal).
- Scoped (host/web/src + layer1b + layer2 + ems_exec + host/server.py): 126 files, +3349 / −2749.
- 16 dead fill fns deleted under host/web/src/cmd/fill; total per-lane `dels` reported in FIX RESULTS sum to ~65 dead-logic removals.

### Remaining (out of this gate's scope)
- col_dict.latest_nonnull() unguarded ghost-table query (robustness; layer1b lane) — see note above.
- The one skipped/deselected live test `test_available_pages` is a transient :8200 LLM outage artifact, unrelated.
- No broad 18-page/25-prompt sweep run (explicitly deferred to the user's acceptance step).

VERDICT: offline gate GREEN; all four targeted confirms PASS; both services live and healthy on the fresh (current-code) host.
