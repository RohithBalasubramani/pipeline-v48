
## PREFLIGHT (read-only gates) — 2026-07-04
### Gate 1 — health + infra
- `curl /api/health` → `{"ok": true, "sb_base": "http://100.90.185.31:6008"}` (OK)
- `:5433` probe → OPEN (neuract reachable; ground-truth cross-checks viable)

### Gate 2 — FRAMES=PAYLOADS (no card routes payload THROUGH a socket/frame mapper)
Grep of host/web/src/cmd/fill/** for `map*SocketToSnapshot|map*ToFrame|assetPageSocket|build*ViewModel(`:
- ALL `ems_backend`/`socket`/`SocketToSnapshot`/`mapVoltageCurrentSocketToSnapshot`/`mapTapRtccToFrame` hits are in COMMENTS (documenting the RETIRED path) or `import type { ChartFilterParams } from "@cmd-v2/realtime/assetPageSocket"` (a TYPE-only import for the date-picker vocab — no runtime call).
- 5 non-comment `build*ViewModel(...)` CALL sites (dg-operations-runtime, transformer-thermal-life, transformer-tap-rtcc, dg-engine-cooling, dg-fuel-efficiency view-model.ts). Inspected: each feeds the card's OWN CMD_V2 producer an EMPTY typed scaffold (emptyOpsSnapshot / emptyEngineFrame / emptyFuelFrame / locally-built empty snapshot+timeline+aging) ONLY to derive the tab's honest empty-state chrome. REAL data path is `payload.<slice>` read direct and passed as `vm=`. This IS the sanctioned FRAMES=PAYLOADS pattern (reuse the card's own producer over an empty base), NOT the retired live-frame→mapper path.
- VERDICT: CLEAN. No offending file:card. ems_backend fully retired from the render path.

### Gate 3 — RENDERER coverage (18 routable pages)
- routable_pages = 18 (enabled). 70 unique card_ids across their page_layout_cards.
- Coverage = union(SPECIAL{8,28,60}, COMPONENTS{57 keys}, COMPOSE{5,6,160}, FILL{12 barrels}).
- MISSING (no renderer in any tier): NONE (70/70 resolve).
- DUP card_id across fill barrels: NONE. All 12 barrels export CARDS; each folder's card-*.tsx files exactly match its CARDS keys.
- 35 cards appear in BOTH COMPONENTS and FILL — NOT a conflict: registry tier order (SPECIAL>COMPONENTS>COMPOSE>FILL) resolves COMPONENTS first; FILL is the documented last-resort fallback.
- UPS pages (50–59) have NO fill folder — correctly served by COMPONENTS. Cards 12/13 (energy-distribution) → Cmp5/CmpEF13 (COMPONENTS).
- VERDICT: CLEAN. Full renderer coverage, no duplicates.

## BATCH 6 (pages 16-18, UPS asset GIC-01-N3-UPS-01) — 2026-07-04
Ground truth: registry_asset 124 / lt_mfm id 11 / table gic_01_n3_ups_01_p1 (72-col standard MFM electrical table, class UPS). LIVE data fresh to 2026-07-04 19:46 (apparent_power_total_kva~195, PF, V, I, freq all real). NO battery/SOC/temperature/autonomy/transfer columns exist → those leaves MUST be honest-blank.

### Page 16 — 'ups battery and autonomy' → ups-asset-dashboard/battery-autonomy (200, 97s)
- routed_ok: YES (UPS asset → UPS battery-autonomy tab, class-appropriate). asset resolved mfm_id 11, no pending, has_data.
- cards 50/51/52/53 all present, has_payload, no payload_error.
- card 50 Battery Health: honest_blank, all leaves '—' + reason "X not measured by this meter" — CLEAN honest-gap.
- card 51 Battery Health History: partial, series values=[] + per-leaf reason — CLEAN honest-gap.
- card 53 Backup Readiness History: partial, series values=[] + reason — CLEAN honest-gap.
- card 52 Backup Readiness: DEFECT — render honest_blank/partial (score null, metrics '—') BUT served payload leaves surviving Storybook seeds `deltaLabel:"-12"` and `Transfer Mode:"Inverter"` (from card_payloads default "48/100 (-12 vs ready) ... on Inverter"). Frontend will render a fabricated -12 delta chip + Inverter mode with no source column. Violates contract (d) no surviving seed. layer=[ems_exec/validate].
- NOTE: notes.loop1 prose claims "showing battery SOC/DC Bus/Thermal derived columns" — FALSE optimism; render truth-layer correctly blanked them. Prose is telemetry, not a render gate; not itself a defect but misleading.

## BATCH 5 (pages 13-15) — adversarial sweep @ 2026-07-04

### Page 13 | 'dg operations and runtime for DG-1' | expected diesel-generator-asset-dashboard/operations-runtime
- asset_pending on 1st POST → 2 DG candidates (mfm_id=2 DG-1 MFM has_data=true; mfm_id=300 GIC-28-N1-DG-01 has_data=false). Re-POST asset_id=2 (class-matched, name "DG-1"). 110s.
- routed=diesel-generator-asset-dashboard/operations-runtime — MATCH. shell DgAssetDashboard, class DG. routed_ok=true.
- 4 cards (70,71,72,73), all conforms=true, fill_ok=true, payload_error=None, seed=0, 0 NaN.
- card70 render (real=9): topKpis real (27727.707 energy, 0 power idle). CROSS-CHECK seed payload: seed had topKpis '4,300'/'295'/'99.9', ceiling 300, warnPct 85, avail 99.88 — ALL overwritten (rendered 27727.707/0/0, 500/80/99.5). NO surviving seed. ceiling/warnPct/availability = nameplate/config metadata, not seed. PASS.
- card71 partial (real=2): honest gaps duty.label(col absent), runHours/loadPct/loadFactor(active_energy/active_power below-range). CROSS-CHECK neuract dg_1_mfm: active_power_total_kw min=max=avg=0 across 41828 rows (DG idle) → 0-power honest-blank defensible; active_energy_import_kwh CONSTANT 27727.707 all rows (frozen counter) → delta=0 honest-blank defensible. HONEST GAPS.
- card72 partial (real=3): honest gaps reactive_energy_import/export_kvarh — CONFIRMED cols DO NOT EXIST in dg_1_mfm. HONEST GAPS.
- card73 honest_blank (real=0): bucket_label(absent), active_energy(frozen), reactive_energy(0 kvar idle), demand_limit(absent). Underlying data idle/frozen/absent per neuract. HONEST GAPS, per-leaf reasons, not whole-card refuse.
- DEFECTS: none. honest_gaps on 71/72/73.

## ADVERSARIAL SWEEP batch 3 — 2026-07-04 (reviewer: subagent)
### infra: :5433 OPEN, :8770 OPEN. Ground-truth cross-checks viable.

### PAGE 07 | 'real time monitoring for GIC-01-N3-UPS-01'
- ROUTED: individual-feeder-meter-shell/real-time-monitoring (EXPECTED match). routed_ok=TRUE.
  reconcile note: asset has_feeders=False → moved OFF panel-overview-shell to feeder-meter shell. CORRECT class handling.
- ASSET: GIC-01-N3-UPS-01 CL:600KVA, class=UPS, mfm_id=11, table=gic_01_n3_ups_01_p1, has_data=True. AI-resolved, no pending. class-appropriate.
- CARDS 3/3 render real component payload-direct, no payload_error:
  - 36 Power&Energy: REAL (activePower 185kW, apparentPower 185.6kVA, reactive 9.9kVAR). projectedDemand='—' honest-blank, reason "sensor below valid range". CROSS-CHECK neuract active_power_total_kw = -196..-211 (NEGATIVE) → worstPeakKw correctly rejects → honest_gap VALID, not a defect. ok=TRUE honest_gap=TRUE.
  - 37 Voltage: REAL series 3-phase LN ~229-240V (neuract voltage ~234-239V ✓). metrics Avg236/Max237.5/Min234.8 real. render seed:1 = data.thresholds label "Max-420V/Min-400V" (design limit chrome; NO neuract threshold column exists → unfillable seed). pipeline HONESTLY flags partial+seed:1. LEAF-level seed on limit-band chrome. ok=TRUE honest_gap=TRUE (minor: threshold band carries seed limit).
  - 38 Current: REAL series 3-phase ~255-290A (neuract current 271-310A ✓). metrics Max270/Min255/Avg262/Neutral13 real. render seed:1 = data.thresholds "Max-120A/Min-100A" band — 120A limit vs 270A real; NO neuract threshold col → unfillable seed. pipeline flags partial+seed:1 honestly. ok=TRUE honest_gap=TRUE (minor threshold seed).
- DEFECTS: none hard. NOTE: threshold-limit band leaves (37,38) carry Storybook seed values (420V/400V, 120A/100A) with no neuract source column; declared metric current_high/low_threshold_a does not exist in neuract → permanently unfillable design chrome. Pipeline flags honestly (partial+seed). Borderline vs contract-(d) "no surviving seed" but it is non-measurement limit chrome + honestly flagged.

## BATCH 4 — page 10 (dg voltage/current DG-1) — 2026-07-04
- 1st POST → asset_pending, 2 candidates BOTH class=DG (no cross-class leak, good). Re-POST asset_id=2 (DG-1 MFM, has_data:true).
- routed = diesel-generator-asset-dashboard/voltage-current ✓ (expected). asset=DG-1 MFM class DG how=user-choice ✓. 4 cards (66,67,68,69), no payload_error, no NaN/Inf.
- GROUND TRUTH neuract.dg_1_mfm: 41845 rows thru 2026-07-04 19:48 (LIVE). voltage_ll_avg/voltage_ry/current_r/current_avg ALL literally 0 (max=min=0 across all rows). Only non-zero: active_energy_import_kwh (accumulator 27727), phase_angle_deg=90, kpi_voltage_deviation_pct=-100. => genset IDLE; all-zero V/I payloads are REAL, not fabrication. markerPct:-100.0 correctly reflects deviation.
- DEFECTS (surviving Storybook seed / fabricated capacity — contract d):
  * card 66 .data.summary.nominal='11.0' (kV) — SEED-identical; real DG-1 nameplate nominal_voltage_ll=415.0 V (0.415kV), a 415V LV genset, NOT 11kV. Fabricated nominal. [ems_exec/validate]
  * card 66 .data.summary.deviation='+0.2' — SEED-identical; contradicts value=0 & markerPct=-100. Stale seed. [ems_exec/validate]
  * card 69 .data.maxLine={label:'Rated: 131A', value:131} — SEED-identical; DG-1 has NO rated_kva (registry+nameplate empty, source='none'). Fabricated rated-current reference line. [ems_exec/validate]
- honest_gaps (blank-with-reason, PASS/telemetry): card66 metrics[2].value "Spread" ("voltage_avg not measured by this meter"); card67 history.maxY ("Rated capacity unknown for dg_1_mfm — loading% unavailable"); card68 metrics[1] ("Sensor reading below valid range"); card69 stats[2] ("Sensor reading below valid range").
- cards 67,68 clean (0 surviving numeric seeds). band ±10 labels + stat labels = static chrome, not defects.

## ADVERSARIAL SWEEP batch 1 — 2026-07-04
### Page 01 | 'real time monitoring for PCC Panel 1'
- routed = panel-overview-shell/real-time-monitoring (EXPECTED match). asset = PCC-Panel-1 mfm 317, class Panel, has_data+has_feeders. routed_ok=TRUE. No asset_pending.
- 8 cards; all has_payload, all validation verdict=pass, seed=0 everywhere (no Storybook seed leak), no NaN.
- GROUND TRUTH (neuract 5433): pcc_panel_1_feedbacks = BREAKER/STATUS table (ACB on/trip fb, winding temps) — NO voltage/current/pf/active_power cols. Electrical metrics live in 8 member feeders (mfm 11,12,13,16,20,23,24,25). 4 members reporting live (n3-ups-01,n4-ups-02,n5-ups-03,n8-bpdb-01: V≈236.8, I≈273-436, kW live @19:49); OTHER 4 (n2-bpdb-02,n5/6/7-ups-04/05/06) have 0 rows (genuinely empty). So _coverage 4-of-8 is HONEST.
- Card 9 (Total Feeder Consumption): supply 933.2 kW REAL (sum_magnitude over 4 reporting members), denominator '—' honest. OK.
- Card 7 (Context Rail): railVM.trend.series = 25 REAL aggregated pts (985,909,...), PowerFactor 0.992 REAL, supply 933.2 REAL; only 'Peak Today' honest-blank '—'. OK + minor honest_gap.
- Card 5 (Feeder Heatmap): payload_error=llm timeout (~32.5K tok) — KNOWN fail-fast; STILL renders default metadata + ems_exec real data: 4 members real kw (191/188/192.2/362 ≈ DB), 8 feeders honest-blank '—'. OK + honest_gap (empty-table members). Timeout noted (contract-e soft).
- **DEFECT — Card 10 (Consumption Trend)**: series:[] + bottomStats Peak/PF = 0.0, yet verdict=render/answerability=full/gaps=0. Ground truth: active_power_total_kw + power_factor_total are LIVE in 4 members (card 7 built the SAME 25-pt series + PF 0.992 successfully). The ems_backend real-time consumer (consumers/real_time_monitoring/pcc_panel.py) returned zeros instead of aggregating reporting members. Fabricated 0.0 masked as full render. layer=ems_exec (+ validate: 0.0 not flagged as blank).
- **DEFECT — Card 11 (Quick Stats)**: Voltage/CurrentUnbal/Electrical-load all = 0.0, verdict=render/answerability=full/gaps=0. Ground truth: voltage_avg=236.8, current_unbalance_pct=3.66, current_avg=273 LIVE in members RIGHT NOW. Same consumer path returned 0.0. Fabricated zeros as full render. layer=ems_exec (+ validate).
- Cards 6/8/160 = nav/narrative payload-exempt, verdict=render, no data leaves. OK.

### Page 17 — 'ups output load capacity' → ups-asset-dashboard/output-load-capacity (200, 78s)
- routed_ok: YES (UPS asset → output-load-capacity, class-appropriate). asset mfm_id 11, no pending.
- ROOT CAUSE across page: meter reports active_power_total_kw NEGATIVE (-193.9); apparent_power_total_kva POSITIVE (193.2); rated=600kVA in asset_nameplate.rated_kva. |kw|/600 = kva/600 ~= 32% is a valid computable load factor. Derivation kpiKwLoadPctOfRated/loadFactorPct read SIGNED kw → fail 0..100 range → "Sensor reading below valid range — treated as no reading" (denorm_garbage). Missing abs()/sign-norm.
- card 57 UPS Capacity: DEFECT(2). (a) scoreCells all '—' + capacityHeadroom null — the load-factor SHOULD be ~32% real (rated 600 exists, kva positive) → [ems_exec/validate] wrongly blanked. (b) surviving Storybook seed `deltaLabel:"-8"` in served payload. layer=[ems_exec/validate].
- card 58 UPS Load: MIXED. scoreCells Load=193.3kW + PF=-0.999 REAL (matches neuract live). BUT sparkline all 30 pts loadPct=0.0 + averageLoadPct=0.0 — same signed-kw denorm kill; loadPct SHOULD be ~32%. Reason present so borderline-honest, but data verifiably exists → [ems_exec/validate] defect (real leaf blanked). Headroom 0.0kW also wrong (600-193=407 real).
- card 59 Composite: DEFECT. composite.points=[] (n=0) EMPTY. gaps blank inputVoltageV(voltage_avg), inputCurrentA(current_avg), bypassFrequencyHz(frequency_hz) as denorm_garbage — but neuract confirms v 225-240V, i 0-336A, f 49.5-50.7Hz, 52606 non-null rows ALL VALID+LIVE. kpiCells survived (Avg Input Voltage 236.8 real) proving data real. Point-series cascade-killed by shared signed-kw loadFactorPct poison. layer=[ems_exec/validate]. Real time-series wrongly whole-blanked.
- SUMMARY p17: 0/3 cards clean. All 3 hit by the negative-signed-power denorm bug + 57 also carries a -8 seed.

### PAGE 08 | 'energy and power for GIC-01-N3-UPS-01'
- ROUTED: individual-feeder-meter-shell/energy-power (EXPECTED match). routed_ok=TRUE. Same UPS asset (mfm_id 11), class-appropriate.
- CARDS 4/4 payload-direct, no payload_error, seed=0 ALL, no NaN/Inf anywhere.
  - 39 Today's Energy: REAL totalEnergyKwh=231 (neuract active_energy_import/export_kwh exist ✓). verdict=render. ok=TRUE.
  - 40 Power Energy Analysis: REAL 27/37. bars/yMax/yMin honest-blank ('—', bars 0) — cause denorm_garbage on active_power_total_kw (neuract value NEGATIVE -187..-211) + data.bars[*].time column_absent. per-leaf reasons present. ok=TRUE honest_gap=TRUE.
  - 41 Input vs Output Energy: hvInputKw=lvOutputKw=187 REAL (=abs active_power_total_kw ~187-191 ✓; single-meter UPS shows one reading twice). lossKwh/deltaPct/efficiencyPct='—' honest — hv_input_kw/lv_output_kw columns ABSENT (verified: UPS meter doesn't measure transformer HV/LV) + loss derivation unbound + denorm. ok=TRUE honest_gap=TRUE. NOTE minor asymmetry: same neg column abs'd-accepted for display leaves but fn-rejected for derived leaves (both conservative, not fabrication).
  - 42 Load Anomalies: actualLoad/loadFactorPct/presentValuePct '—' honest — denorm_garbage on negative active_power_total_kw. per-leaf reasons. ok=TRUE honest_gap=TRUE.
- CROSS-CHECK: active_power_total_kw & reactive_power_total_kvar NEGATIVE in neuract (-187/-10) → denorm rejection CORRECT (not a masked live column). hv_input_kw/lv_output_kw/time/loss columns confirmed ABSENT → column_absent CORRECT.
- DEFECTS: none. All degrades are honest per-leaf with valid reasons; primary energy/power values real.

### Page 14 | 'transformer tap and rtcc for Transformer-01' | expected transformer-asset-dashboard/tap-rtcc
- 1st POST (no asset_id): asset_pending, page_key=transformer-asset-dashboard/tap-rtcc (metric=tap) — CORRECT page. 3 Transformer candidates: mfm_id=171 GIC-15-N3-PCC-01 (Transformer-01) has_data=true; 100174 PQM Transformer-1 Incomer has_data=true; 306 33KV Main Txr-1 Feeder has_data=false. Class-matched name "Transformer-01" = 171.
- Re-POST asset_id=171. 116s. **routed=transformer-asset-dashboard/THERMAL-LIFE (metric=temperature) — MISMATCH vs expected tap-rtcc.** routed_ok=FALSE.
- WHY: reflect/preflight re-route. loop1 notes evaluated tap-rtcc cards (78 Tap Position/80 Recent Tap Changes answerability=none; 81 Tap Activity partial-proxy) → Txr-01 has NO tap/rtcc/oltc columns → pipeline SILENTLY re-routed OFF the user's explicit "tap and rtcc" request to thermal-life. loop2 note contradictorily says "page NOT re-routed" yet final=thermal-life (preflight_reroute fired first).
- CROSS-CHECK neuract gic_15_n3_pcc_01_transformer_01_se: 70 cols, tap/rtcc/oltc/winding/oil/thermal/hotspot cols = NONE (only pf_gap_vs_full_load). So the asset answers NEITHER tap-rtcc NOR thermal-life — the re-route to thermal-life was pointless (thermal cards also honest-blank).
- DEFECT #1 [layer1a/harness reflect-reroute]: silent page swap away from explicitly-requested tap-rtcc to an equally-empty thermal-life. Contract says per-leaf honest-blank on the REQUESTED page, not swap to a different page. The user asked for tap+rtcc; got thermal.
- Cards that RENDERED (thermal-life 74,75,76,77): all conforms=true, fill_ok=true, payload_error=None, seed=0, 0 NaN.
  - card74 Thermal Life: render.verdict=render/answerability=FULL but leaf_stats real=0/data=0, validation=FAIL ("no usable numeric column"). Payload shows winding/oil/loss = 0.0, stressPct=0.0 with EMPTY gaps (no per-leaf reason). SEED was 44/52/49.3/13 — OVERWRITTEN to 0 (no surviving seed, good). DEFECT #2 [layer3/grounding]: 0.0°C temps rendered as values with NO honest-blank reason + verdict "render/full" contradicts real=0. Zeros for unmeasured thermal leaves should be '—'+reason, not 0.
  - card76 Thermal Timeline partial real=27/37: hotspot/oil/winding/ts absent (honest), loadPct/efficiency below-range (idle). honest gaps.
  - card75 Life & Capacity partial real=2/6: life-remaining/derated columns absent (honest). honest gaps.
  - card77 Insulation Aging partial real=23/61: FAA/LoL proxies off active_power below-range (idle). honest gaps.
- DEFECTS: #1 reroute-off-requested-page (layer1a/harness), #2 card74 zero-render-no-reason (layer3). honest_gaps: 75,76,77 (+74's non-zero framing is the defect).

## BATCH 4 — page 11 (dg engine and cooling DG-1) — 2026-07-04
- asset_pending → re-POST asset_id=2 (DG-1 MFM). routed=diesel-generator-asset-dashboard/engine-cooling ✓. asset=DG-1 MFM DG how=user-choice. 3 cards (60,61,62). no payload_error/NaN.
- GROUND TRUTH: neuract.dg_1_mfm has ZERO engine/thermal/coolant/exhaust/oil/press/rpm/speed/load columns (0 of 35 cols match; pure electrical MFM). => all engine-cooling leaves have NO measuring column → honest blanks are CORRECT (not [ems_exec] misses).
- card 60 Engine 3D Callout Viewer: SPECIAL[60] Asset3dEnvelope, equipment.id=2 (real DG-1), answerability=full watermark=live, no GLB→honest ComingSoon placeholder. PASS.
- card 61 Thermal Timeline: series all empty w/ reason ("Sensor reading below valid range; ts not measured"). kpis Peak-Exhaust/Max-Coolant show 0.0°C (should be '—' like card62 does) — telemetry nit, NOT a seed (seed was 656/101, replaced). events markers value 95/104 = trip/warn thresholds (chart chrome), NOT measured. leaf_stats.seed=0.
- card 62 Pressure·Speed·Load: kpis Peak/Avg Load='—' (honest), Min Oil-P 0.0. series empty w/ reason. seed kpi 99/82/177 correctly REPLACED. leaf_stats.seed=0.
- SEED CHECK: render layer reports seed:0 on all 3; my payload-vs-seed diff confirms NO surviving Storybook NUMBER (only static axis-domains / trip-warn setpoints / labels survive = chart config chrome, not data). CLEANER than page 10.
- DEFECTS: none rising to seed/fabricated-capacity. honest_gaps: card61 series×4 + kpis[2]; card62 series×2 + kpis[0,1]. (card61 0.0°C-vs-'—' logged as minor inconsistency, not a defect.)

### Page 02 | 'energy and distribution for PCC Panel 1'
- routed = panel-overview-shell/energy-distribution (EXPECTED match). asset PCC-Panel-1 mfm 317 Panel. routed_ok=TRUE. No asset_pending. 2 cards.
- GROUND TRUTH 24h energy deltas: n3-ups-01 export=4674 (import 0); n4=4683; n5=4680; n8-bpdb-01 import=78380 (export 0). Other 4 members 0 rows.
- Card 12 (Energy Input & Distribution / rail sankey): panel stage node=78310 REAL (≈n8 import 78380); n8-bpdb meter=78310 REAL; incomer sources=null honest; 4 empty members=null honest. BUT n3/n4/n5 UPS meters=0.0 while each moved ~4674 kWh EXPORT — aggregation counts import-only, so exporters read 0.0. Soft convention gap (import genuinely 0), members' export energy under-reported. seed=0,no NaN. Card renders real component. OK + honest_gap (null members) + soft note (UPS export 0.0).
- **DEFECT — Card 13 (Energy Flow Diagram)**: sankey has REAL 78350 throughput (panel→bpdb link), yet KPI band = sourceInputKw 0.0 / feederOutputKw 0.0 / efficiencyPct 0.0 / lossKw 0.0 / lossPct 0.0 — ALL zeros, verdict=partial, NO honest-blank '—' + NO gap reason. Internally inconsistent (78350 flows but 0 input/0 output/0% eff). Fabricated-by-zero KPI leaves not derived from the same aggregate the sankey used. layer=ems_exec/validate. (UPS export members also 0.0 same as card12.)
- Both: gaps arrays EMPTY despite null/0.0 leaves — per-leaf honest-blank telemetry not emitted for these (nulls still render blank in component; the 0.0 KPIs are the fabrication concern).

### Page 18 — 'ups source transfer' → ups-asset-dashboard/source-transfer (200, 72s)
- routed_ok: YES (UPS asset → source-transfer, class-appropriate). asset mfm_id 11, no pending.
- card 54 Transfer readiness: DEFECT. score null + all metrics '—' correct (input/bypass/sync scores unmeasured), BUT surviving Storybook seed `deltaLabel:"+36"` (byte-matches card_payloads default). Frontend renders fabricated +36 delta chip. layer=[ems_exec/validate].
- card 55 Activity: DEFECT. count30d/lastTransferDays/lifetimeTransfers correctly null, BUT `ticks` array [F..T(7)..T(24)..F] is BYTE-IDENTICAL to Storybook default → 2 fabricated transfer-event blips shown with NO transfer-event source column. Surviving seed. layer=[ems_exec/validate].
- card 56 Composite: DEFECT(2). (a) composite.points=[] EMPTY — blanks voltage_ll_avg(389-416V,52612 rows), current_avg, frequency_hz all VALID+LIVE as denorm_garbage (signed-kw cascade). Same as card 59. (b) FABRICATION: kpiCells "Transfers today"=-192.7 == active_power_total_kw (mislabeled negative power leaked into a transfer-count leaf). Worse than a seed — wrong-metric real column in a semantically-wrong slot. kpiCells Avg Input Voltage 410.9 IS real. layer=[ems_exec/validate].
- SUMMARY p18: 0/3 clean.

## BATCH 6 VERDICT
- ROUTING: 3/3 pages routed correct + class-appropriate; asset GIC-01-N3-UPS-01 pinned every time (mfm_id 11, no pending, no wrong-class candidate). Layer1/asset-resolver CLEAN.
- RENDER PATH: every card renders its real CMD_V2 component payload-direct, has_payload, zero payload_error. Frames retired confirmed.
- HONEST GAPS (genuine, PASS): p16 cards 50/51/53 (battery/backup domains have no source column — every leaf '—' + reason). CLEAN.
- DEFECTS (9 total, all layer [ems_exec/validate]):
  1. Signed-power denorm bug (root): active_power_total_kw negative (-193) fails loadFactorPct/kpiKwLoadPctOfRated 0..100 range → "sensor below valid range" wrongly blanks REAL ~32% load-factor (kva positive, rated 600 in nameplate). Hits p16#52, p17#57/#58/#59, p18#54/#56.
  2. Composite point-series whole-blank: p17#59 & p18#56 render 0 points though voltage/current/frequency are live+valid (kpiCells prove data real). Cascade from #1.
  3. Surviving Storybook seed deltaLabels/ticks in served payloads: p16#52 (-12 + "Inverter"), p17#57 (-8), p18#54 (+36), p18#55 (ticks bitmap). Byte-match card_payloads defaults — validate layer strips score/metrics but misses these chrome leaves.
  4. Wrong-metric fabrication: p18#56 kpiCells "Transfers today"=-192.7 == active_power_total_kw leaked into a transfer-count slot.

## BATCH 4 — page 12 (dg fuel efficiency DG-1) — 2026-07-04
- asset_pending → re-POST asset_id=2 (DG-1 MFM). routed=diesel-generator-asset-dashboard/fuel-efficiency ✓ metric=fuel. asset=DG-1 MFM DG. 3 cards (63,64,65). validation.verdict=fail (all fuel leaves unmeasurable — expected). no payload_error/NaN.
- GROUND TRUTH: dg_1_mfm has NO fuel column (no level/burn/temp sensor). Has energy/power cols but ALL power=0 (idle) and active_energy_import_kwh is a FLAT accumulator (max=min=27727.707). => every fuel/efficiency leaf must be blank; windowed totalKwh delta=0.
- card 63 Fuel Tank Anatomy: ALL leaves null (autonomy/fuelRate/fuelTemp/fuelLevel/efficiency + title/subtitle/aiText). 5 gaps cause=column_absent w/ reasons. PASS (fully honest).
- card 64 All Runs (Fuel Log): faults/starts/avgLoad/runHours/totalFuelL=null w/ reasons (column_absent / no_nameplate). totalKwh=0.0 = REAL windowed delta of a flat accumulator (defensible, not fabrication). seed=0.
- card 65 Fuel & Tank Composite: kpis Efficiency='—', series empty w/ reasons naming exact absent cols (dg_fuel_level_pct/dg_fuel_burn_rate_lph/dg_fuel_temperature_c). kpi gaps cause=denorm_garbage/no_nameplate. seed=0.
- SEED CHECK: cards 63/64 have ZERO non-zero numeric payload leaves. card 65's 33 seed-identical leaves are ALL chart chrome (axis width/domain, hex colors, '-16h/-8h' time labels, warn:20 '20% low' threshold annotation, dash/area/width) — NO measured fuel NUMBER survives. render leaf_stats.seed=0 on all 3.
- DEFECTS: none. honest_gaps: card63 ×5, card64 ×5, card65 ×6. EXEMPLARY honest degradation — every blank has a per-leaf cause+reason.

### PAGE 09 | 'power quality for GIC-01-N3-UPS-01'
- ROUTED: individual-feeder-meter-shell/power-quality (EXPECTED match). routed_ok=TRUE. metric=thd. Same UPS asset, class-appropriate.
- CARDS 3, seed=0 ALL, no NaN/Inf, no payload_error.
  - 47 Power Quality: iThd valuePct=7.77 REAL (=thd_compliance_i_avg, matches thd_current avg ~7.7 ✓). h5/h7/vThd valuePct=1.0 via thdComplianceIeee519 fn (derived compliance floor, not raw measure). verdict=render seed=0. ok=TRUE. minor: vThd compliance shows 1.0 while raw voltage-THD unlogged — but it's a derived compliance fn, not a raw claim.
  - 48 Distortion & Harmonic Profile: i-thd view 3 series REAL 25/25 (R 8.49, Y 7.66, B 5.85 — matches neuract thd_current_r/y/b ✓). v-thd view 3 series ALL None honest-blank — CROSS-CHECK: thd_voltage_r/y/b_pct columns EXIST but EMPTY ('') for ALL 52611 rows → 'not logged by this meter' CORRECT structurally_null. h5-h7 view 0 series (harmonics not measured). ok=TRUE honest_gap=TRUE. minor UX: default active view=v-thd (the blank tab) while i-thd has real data.
  - 49 Load Impact & Transformer Stress: **DEFECT**. Active default view=pf-health shows Power Factor=0.0, True PF=0.0, PF Gap=0.0, PF Target=0.0; pf-angle view Phase angle=0.0. CROSS-CHECK neuract: power_factor_total=-0.999, kpi_true_pf=0.99, phase_angle_deg=177.4, pf_gap_vs_full_load=-1.99 — LIVE for 52615 rows. These slots are NOT in data_instructions (only k-stress view bound → k_factor honestly '—'/None). The pf-health & pf-angle leaves were zeroed (default 0.909/0.857/19.0 stripped to 0.0) and COUNTED AS REAL (leaf_stats real:8/data:11, only 2 gaps, both k-stress). 0.0 renders as if measured PF — NOT honest-blanked, NO reason. seed sentinel misses it (stripped-to-0.0 ≠ 0.909 default, and dv!=0 guard). VIOLATES contract (c) meter-measures-PF-but-shows-0.0 + (d) 0.0 not a real reading. layer=ems_exec/validate (unbound non-default views + validate scores zeroed leaves as real). ok=FALSE.
- DEFECTS: [ems_exec/validate] card 49 pf-health(active)+pf-angle views show 0.0 for Power Factor/True PF/PF Gap/PF Target/Phase angle while neuract power_factor_total/kpi_true_pf/phase_angle_deg have live data (52615 rows); slots unbound in data_instructions, zeroed leaves counted real (no honest-blank).

### Page 15 | 'transformer thermal life for Transformer-01' | expected transformer-asset-dashboard/thermal-life
- 1st POST: asset_pending, page_key=transformer-asset-dashboard/thermal-life (metric=temperature) — CORRECT. Same 3 Txr candidates. Pin 171 (Transformer-01, has_data).
- Re-POST asset_id=171. 51s. routed=transformer-asset-dashboard/thermal-life — MATCH. routed_ok=TRUE. NO re-route (loop2=null). how=user-choice.
- 4 cards (74,75,76,77) all conforms=true, fill_ok=true, payload_error=None, seed=0, 0 NaN.
- card74 Thermal Life partial real=1/data=5: Winding/Oil/Loss temps render '—' °C/kW (CORRECT honest-blank, unlike page14 same-card 0.0 bug). hotspot/thermal cols absent. HONEST GAP. (statusLabel still 'Normal' on blank temp = cosmetic metadata, minor.)
- card75 Life & Capacity partial real=4/6: lifeFill (active_energy_import_kwh NULL-all), deratedFill (active_power below-range). CROSS-CHECK: active_energy_import_kwh EXISTS but count=0 (all NULL) → "not logged" honest. HONEST GAP.
- card77 Insulation Aging partial real=12/61: FAA off power_factor, hotspotPeak off voltage_avg "below valid range". CROSS-CHECK neuract: voltage_avg REAL (avg 6450V, 2486 rows), power_factor REAL (0.997). Blanking them for a HOTSPOT-TEMP proxy is OUTCOME-correct (voltage is not a temp) but the REASON string "below valid range" is a MISLABEL (real reason = wrong-proxy). Minor reason-string defect.
- **DEFECT [ems_exec/validate] — card76 Thermal Timeline legend-leak (REPRODUCES on page14 AND page15):** timeline.points=[] EMPTY, but legend leaks RAW un-normalized values: Load = -774/-849 with unit '%' (raw active_power_total_kw kW), Efficiency = 777/852 with unit '%' (raw apparent_power_total_kva kVA). CROSS-CHECK neuract: transformer IS live — active_power ~-944kW (real signed export), apparent_power ~948kVA (real positive), pf 0.997, V 6493 — 2486 rows. So (a) the loadPct/efficiencyPct proxy never normalizes kW/kVA→% (shows -774 as "Load %", 777 as "Efficiency %" — physically nonsensical, fabrication-adjacent), AND (b) the series points render empty while real load data exists. This is the same denorm_garbage "below valid range" filter rejecting NEGATIVE active power as invalid + not building the series.
- card76 leaf_stats real=33 is INFLATED: 24 of the 33 are axis tick timestamps + 6 axis min/max config + hotspotWarnC — axis metadata, NOT measured data. Only 2 actual measured leaves (the 2 leaked legend values). Grounding counts axis metadata as "real data" — telemetry over-counts.
- DEFECTS: #1 card76 legend-leak/empty-series (ems_exec/validate). honest_gaps: 74,75,77. routed_ok TRUE.

## ADVERSARIAL SWEEP batch 2 (pages 04,05,06) — 2026-07-04
Infra: host :8770 health OK; neuract :5433 OPEN (target_version1/neuract). All 3 routed to expected pages, class-appropriate assets (04/05→mfm317 PCC-Panel-1 Panel; 06→mfm11 GIC-01-N3-UPS-01 UPS). Registry registry_lt_mfm_outgoing links 317→{11,12,13,16,...} so the GIC feeders under PCC-Panel-1 are TOPOLOGICALLY correct (not mis-binding).

### PAGE 04 harmonics-pq (5 cards)
- card 26 (feeder PQ table), 27 (signature radar): CLEAN — 4 REAL gic feeders, real kw/iThd, vThd honest-null (thd_voltage_* empty in neuract). PASS.
- card 23 (KPI strip): MIXED — worstIThd REAL (GIC-01-N3, iThd 7.17) but `worst` sub-object = SEED (ups-05/MFM_034/status danger, all 0.0). DEFECT [ems_exec] surviving seed in worst-leaf.
- card 24 (timeline): payload_error='llm call failed (timeout) ≈25890 tok' + conforms=False (contract (e) violation). Data real but 8 timeline periods are an IDENTICAL replicated snapshot (iThd 7.17 flat) while neuract has 3319 varying rows/24h → temporal axis fabricated-flat. DEFECT [ems_exec].
- card 25 (AI summary): narrative .text is REAL/grounded (names GIC-01-N3, 8.4% vs 8.0%). BUT structured summary.period.panels[] = 10 fabricated seed panels ups-01..06/bpdb/hhf tables MFM_023..061 (NONE exist in neuract) all-zero + worst/worstIThd/worstVThd seed. leaf_stats seed=0 (detector missed string seeds). DEFECT [ems_exec] surviving seed.

### PAGE 05 voltage-current (5 cards) — SYSTEMIC
- ALL 5 cards (18,19,20,21,22): real=0/data=0 yet verdict=render/full/reason=null (dishonest). Every period.panels[] = fabricated seed ups-01..05 / MFM_025..034 (confirmed NON-existent in neuract; byte-identical to card_payloads Storybook default) with all-0.0 numbers. card18 worstCurrent/worstVoltage = seed (ups-04/MFM_033, ups-05/MFM_034/upsInrush/danger). filterSelection.rangeEnd='2026-06-29' stale seed date. Real PCC-Panel-1 feeders (gic_01_n3_ups_01_p1 …) DO carry live V=237/I=269/In=15.6 as of 19:53 today. DEFECT [ems_exec/validate]: voltage-current panel-aggregate consumer fills NOTHING, retains Storybook seed, mislabels render/full. Contract (d) violation on all 5.

### PAGE 06 voltage-current UPS (4 cards)
- card 46 (current history): CLEAN 115/115. card 44 (voltage history): 109/110, 1 blank 'sensor below valid range' — plausible per-sample QC honest_gap.
- card 43: blanks voltageUnbalancePct + voltageMaxMinGap as 'no derivation binding configured' — but neuract voltage_unbalance_pct=0.90 (live) and voltage_max=239.2/voltage_min=235.6 (live). FALSE honest-blank. DEFECT [validate] missing derivation binding.
- card 45: blanks max_gap 'no derivation binding for current_spread_br' — but neuract current_spread_br=10/10/8 (live). FALSE honest-blank. DEFECT [validate].
- 'ts not measured by this meter' on card 43 = legit (per-meter tables have timestamp_utc but the story wants a bucketed ts leaf) — honest.

### Page 03 | 'energy and power for PCC Panel 1'
- routed = panel-overview-shell/energy-power (EXPECTED match). asset PCC-Panel-1 mfm 317 Panel. routed_ok=TRUE. No asset_pending. 4 cards.
- All 4 cards use consumer consumers/energy_power/pcc_panel.py (NOT present on disk; like real_time consumer). All return ALL-ZERO data yet verdict=render/answerability=FULL/gaps=0.
- GROUND TRUTH (n8-bpdb-01 member, live now): apparent_power_total_kva=498, active_power_total_kw=491, reactive_power_total_kvar=24; active_energy_import_kwh cum=2,631,440 (24h delta 78,380). Page-02 card12 aggregated this SAME n8 import to 78310 successfully — so data + aggregation demonstrably exist.
- **DEFECT — Card 14 (Cumulative Energy)**: value/Active/Reactive/SEC all 0.0, segments:[], verdict=render/full/gaps=0. Metrics active_energy_import_kwh+reactive+apparent LIVE in members. Fabricated-zero as full-answer. layer=ems_exec/validate. (target '175.6' / markerLabel '169' = metadata threshold labels, unverified nameplate.)
- **DEFECT — Card 16 (Energy Consumption Trend)**: UPS/BPDP/HHF legend 0.0, points:[], 7 totals 0.0 with SEED date labels 'Apr 15,16,17,18,19,20,21 (Today)' — SURVIVING STORYBOOK SEED (today=Jul 04). Seed-leak (contract-d) + fabricated-zero + full-answer verdict. layer=validate/seed + ems_exec.
- **DEFECT — Card 15 (Today live power analysis)**: Active/Reactive/LoadFactor all 0.0, verdict=render/full/gaps=0. Members have LIVE active_power (n8=491kW) NOW. Fabricated-zero as full-answer. layer=ems_exec/validate. (markerLabel '1,400 Worst Peak' metadata.)
- **DEFECT — Card 17 (Daily Power Demand by Feeder)**: time axis labels '03 19:00..04 19:00' REAL, but ALL point values hhf/ups/bpdp=0.0, Worst Peak/Load Factor 0.0, verdict=render/full/gaps=0. Real per-feeder daily power exists. Fabricated-zero series as full-answer. layer=ems_exec/validate.
- SUMMARY p03: 0/4 cards carry real panel-aggregate data; energy-power panel-aggregate consumer path unwired → all-zero + full-render verdict (worst of the 3 pages). Routing correct.

### BATCH 1 VERDICT
- Routing: 3/3 pages routed to the CLASS-APPROPRIATE panel-overview-shell + bound PCC-Panel-1 (317). Perfect routing. No asset_pending.
- Cards: p01 6/8 ok (cards 10,11 defect), p02 1/2 ok (card13 defect; card12 ok+softnote), p03 0/4 ok (14,15,16,17 defect).
- Root cause cluster: the panel-aggregate REAL-TIME + ENERGY-POWER consumers (consumers/real_time_monitoring/pcc_panel.py, consumers/energy_power/pcc_panel.py) are UNWIRED/absent → those cards emit fabricated 0.0 (NOT honest-blank) under verdict=render/full/gaps=0, while the ROSTER-aggregation path (card 9/7/5/12 rail sankey) correctly aggregates the SAME live members. Card 16 additionally leaks Apr Storybook date seeds. All defects cross-checked against neuract live data. infra_down=false.

## CROSS-CLASS / EDGE prompt batch (9 prompts) — 2026-07-04
Infra: host :8770 up (404 on / = API-only, expected); neuract :5433 OPEN. Zero NaN, zero surviving Storybook seed date, zero payload_error across all 9.

ROUTING: 9/9 class-appropriate. DG→diesel-generator-asset-dashboard; UPS→ups-asset-dashboard OR feeder-meter/voltage-current; Transformer→feeder-meter (rt/voltage/energy per metric); AHU/Spare→feeder-meter. Every named asset present in candidates (recall PASS on all 9).

HOMONYM / PICKER: 8/9 returned asset_pending=True with candidate picker, 0 cards (CORRECT for ambiguous homonyms — no silent wrong-asset render). Only AHU-5 pinned confidently (how=AI) and rendered 4 cards.

- dg03 "Real-time power of DG-03 Jackson" — CRITICAL HOMONYM PASS. Candidates: DG-3 MFM (mfm4, dg_3_mfm, has_data=TRUE, 42008 rows live) vs GIC-28-N3-DG-03 [Jackson] (mfm302, gic_28_n3_dg_03_jk, has_data=FALSE, 0 rows CONFIRMED in neuract). The named "Jackson" asset is genuinely empty; the pipeline does NOT render DG-3 MFM's 42k live rows as the answer — it surfaces both for disambiguation. Exactly the anti-fabrication behavior required. OK.
- ups04/ups01/ups10/tf01/tf03/tf05 — OK. All surface a small (2-5) class-correct picker; named asset present; every candidate is the right class (UPS/Transformer). Homonym instances (e.g. UPS-04 exists at GIC-17-N4, GIC-27-N4, GIC-02-N5) all offered, correct.
- ahu5 "voltage and current health for AHU-5" — confident pin mfm36 (GIC-03-N6-AHU-5, gic_03_n6_ahu_5_p1, 12376 rows). Renders 4 cards (43/44/45/46) all conforms=true, fill_ok=true, ems_exec, verdict pass/pass_with_gaps, 0 NaN, 0 seed. Live phase V (243.4/242.1/245.1) and I (48/51/53/4.36) REAL. See DEFECT below.

DEFECT FAMILIES:
1. **[validate] over-broad candidate recall — 'power quality for a spare feeder' returns 180 candidates across 14 classes** (46 Spare + 134 non-Spare: 44 Panel, 20 UPS, 14 Transformer, 9 AHU/9 DG, 8 Chiller, Pumps/Compressors/APFCR...). The generic "feeder" token bypassed the class filter and dumped nearly the whole registry. Recall is technically satisfied (all Spares present) but precision is broken → picker is unusable at 180 rows. Class-token "spare" should have constrained to the 46 Spare-class (or 16 with-data) candidates.
2. **[validate/ems_exec] AHU-5 false honest-blank on LIVE derivation metrics (REPRODUCES the page06 missing-derivation-binding family):**
   - card43 Voltage Live Health dashes ALL 3 metrics: "Unbalanced %" (neuract voltage_unbalance_pct=0.667 LIVE), "Max gap V" (voltage_max 246.4 − voltage_min 243.6 = 2.8 V derivable LIVE), "Rate Change V/min" (no direct col — plausibly honest).
   - card45 Current Live Health dashes "Max gap A" (current_max 53 − current_min 48 = 5 A; current_max_spread=5.0 exists directly LIVE) — yet card45 SUCCESSFULLY computes Unbalanced=4.4% and Neutral/phase=8.8%. Inconsistent: same derivation blanked on one card, computed on another. These dashes carry no per-leaf reason string and mask live data → contract (c) false-blank, not honest degrade.
   - (Legit honest-blanks on same cards: all delta/deltaText/deltaTone period-over-period deltas — no prior window — and thd_voltage_* which are NULL in neuract.)

SUMMARY: routing 9/9 OK; homonym/picker 9/9 OK (esp. the DG-03 Jackson wrong-asset trap — PASS); zero NaN/seed/payload_error. Two defect families: (1) spare-feeder over-broad 180-candidate recall (precision), (2) AHU-5 (page06-family) false-blank of live unbalance/max-gap derivations.

================================================================================
## FINAL VERIFICATION MATRIX — 18-page acceptance sweep — 2026-07-04
## (reviewer subagent; READ-ONLY; host :8770 + neuract :5433 both OPEN)
================================================================================

### Ground-truth re-confirmed at matrix time (cmd_catalog SELECTs)
- registry_lt_mfm[id=2].rated_capacity_kva = '' (empty)  → DG-1 has NO rated_kva
- asset_nameplate[dg_1_mfm]: rated_kva='' source='none' nominal_voltage_ll=415.0
  → page10 seeds '11.0'kV nominal + 'Rated: 131A' are FABRICATED (real = 415V, no rating)
- asset_nameplate[gic_01_n3_ups_01_p1]: rated_kva=600.0 source='cmd_equipment_table'
  → page17/18 ROOT confirmed: rated 600 EXISTS, ~32% load factor IS computable;
    negative active_power_total_kw denorm-gate wrongly blanks a REAL leaf.

### (1) 18-PAGE × CARD TABLE
nn | page                                   | ok/total | routed_ok | DEFECTS (card:layer)                                             | honest gaps (reason)                                   | infra
01 | panel-overview/real-time-monitoring    | 6/8      | yes       | 10:ems_exec, 11:ems_exec+validate                               | 5,7,9 (empty member tables / worstPeak / coverage 4-of-8) | up
02 | panel-overview/energy-distribution     | 1/2      | yes       | 13:ems_exec+validate                                            | 12 (incomer null / UPS export under-rep)                | up
03 | panel-overview/energy-power            | 0/4      | yes       | 14:ems_exec+validate,15:ems_exec+validate,16:validate/seed+ems_exec,17:ems_exec+validate | —                        | up
04 | panel-overview/harmonics-pq            | 2/5      | yes       | 23:ems_exec,24:ems_exec,25:ems_exec                             | 26,27,24 vThd (thd_voltage_* 0 non-empty rows)          | up
05 | panel-overview/voltage-current         | 0/5      | yes       | 18,19,20,21,22 ALL:ems_exec+validate (SYSTEMIC seed panels)     | —                                                       | up
06 | individual-feeder-meter/voltage-current| 2/4      | yes       | 43:validate,45:validate (FALSE honest-blank, cols LIVE)         | 44 (sensor-below-range), 43 (ts-not-bucketed)           | up
07 | individual-feeder-meter/real-time-mon  | 3/3      | yes       | none                                                            | 36 projDemand (neg power), 37/38 threshold-band (no col)| up
08 | individual-feeder-meter/energy-power   | 4/4      | yes       | none                                                            | 40 bars, 41 loss/eff, 42 loadFactor (neg power/absent)  | up
09 | individual-feeder-meter/power-quality  | 2/3      | yes       | 49:ems_exec+validate (PF/angle 0.0 as-real, cols LIVE)          | 48 vThd empty, 48 h5-h7, 49 k-stress                    | up
10 | diesel-generator/voltage-current       | 1/4      | yes       | 66:ems_exec+validate(×2 seed),69:ems_exec+validate(seed 131A)   | 66 spread,67 maxY,68/69 sensor-range (all with reasons) | up
11 | diesel-generator/engine-cooling        | 3/3      | yes       | none                                                            | 61,62 thermal/oil/rpm series (no engine cols on E-MFM)  | up
12 | diesel-generator/fuel-efficiency       | 3/3      | yes       | none                                                            | 63,64,65 fuel columns genuinely absent (per-leaf reasons)| up
13 | diesel-generator/operations-runtime    | 4/4      | yes       | none                                                            | 71 duty/runHours(idle+frozen ctr),72 reactive-energy,73 | up
14 | transformer/tap-rtcc                    | 0/4      | NO(→thermal-life) | ROUTE:layer1a(silent swap off requested tap-rtcc),74:layer3(0.0 no-reason),76:ems_exec+validate | 75 life cols absent,77 FAA proxy   | up
15 | transformer/thermal-life               | 3/4      | yes       | 76:ems_exec+validate (legend-leak, systemic w/ pg14)           | 74 winding/oil/loss,75 lifeFill,77 hotspot(mislabel)    | up
16 | ups/battery-autonomy                    | 3/4      | yes       | 52:ems_exec+validate (seed -12 + 'Inverter')                   | 50,51,53 battery/SOC/autonomy cols absent (reasons)     | up
17 | ups/output-load-capacity                | 0/3      | yes       | 57,58,59 ALL:ems_exec+validate (neg-kw denorm cascade + seed -8)| —                                                       | up
18 | ups/source-transfer                     | 0/3      | yes       | 54,55,56 ALL:ems_exec+validate (seeds +36/ticks + neg-kw + -192.7 leak) | —                                               | up

### (2) TOTALS
- Cards OK: 37 / 70  (52.9%)
- Cards with DEFECTS: 33 / 70
- Misroutes: 1 / 18 pages (page14 tap-rtcc → thermal-life silent swap)
- Honest-gap cards (PASS, telemetry): counted within OK where the only note is a
  reasoned '—' (pages 07,08,11,12,13 fully honest-clean; plus honest leaves on 01/02/04/06/16)
- Pages fully clean (all cards OK): 07, 08, 11, 12, 13  (5 / 18)
- Pages 100% defective: 03, 05, 17, 18  (4 / 18)

### DEFECT FAMILIES (root-cause rollup)
A. NEG-KW DENORM CASCADE [ems_exec/validate] — active_power_total_kw is signed-negative
   on UPS/feeder meters; a 0..100 valid-range gate blanks (or zeroes) genuinely-real
   load-factor / PF / efficiency leaves though rated_kva & positive kVA make them
   computable. Cards: 49,57,58,59,56 (+ 41/42 conservatively honest). Missing abs()/sign-norm.
B. SURVIVING STORYBOOK SEEDS [ems_exec/validate] — byte-identical default numbers/strings
   survive fill: 66('11.0'kV,'+0.2'),69('Rated:131A'),52('-12','Inverter'),54('+36'),
   55(ticks bitmap),57('-8'),18/19/20/21/22 (ups-0x/MFM_0xx panels),23(ups-05/MFM_034),
   25(10 MFM panels),16(Apr-15..21 date labels). Seed-sentinel misses strings & stripped-0.0.
C. FABRICATED-BY-ZERO as FULL verdict [ems_exec+validate] — all-0.0/empty-series leaves
   reported verdict=render/answerability=full/gaps=0 with NO honest-blank while the metric
   is LIVE. Cards: 10,11,13,14,15,17,74. Panel-aggregate real-time/energy-power/voltage-
   current consumers unwired (real-time consumer file absent on disk).
D. FALSE HONEST-BLANK [validate] — 'no derivation binding configured' blanks a leaf whose
   source columns are LIVE. Cards: 43(voltage_unbalance_pct,voltage_max/min),45(current_spread_br).
   (Cross-class: AHU-5 43/45 reproduce this same family.)
E. MISROUTE [layer1a/harness] — page14 'tap and rtcc' silently re-routed to thermal-life
   after asset pin because Transformer-01 has no tap/rtcc/oltc cols; swap was pointless
   (target equally empty). Contract wants per-leaf honest-blank on the REQUESTED page.
F. LEGEND-LEAK [ems_exec/validate] — card76 (pages 14 AND 15): raw kW shown as 'Load %',
   raw kVA as 'Efficiency %'; empty series; -774/-849 physically nonsensical. Never
   normalizes kW/kVA→% nor builds the series from live 2486-row transformer power.

### (3) FRAMES=PAYLOADS GATE + RENDERER COVERAGE (from preflight, re-affirmed)
- FRAMES=PAYLOADS: CLEAN. Zero offending file:card. All socket/*SocketToSnapshot/*ToFrame
  hits are comments or a TYPE-only ChartFilterParams import. The 5 build*ViewModel() calls
  feed each card's OWN CMD_V2 producer an EMPTY scaffold for empty-state chrome; the REAL
  path reads payload.<slice> direct as vm= (sanctioned pattern). ems_backend retired.
- RENDERER COVERAGE: CLEAN. 18 routable pages, 70 unique card_ids, 70/70 resolve
  (SPECIAL{8,28,60}∪COMPONENTS{57}∪COMPOSE{5,6,160}∪FILL{12 barrels}). No missing renderer,
  no dup card_id across barrels. Every card renders its REAL CMD_V2 component payload-direct.

### (4) CROSS-CLASS VERDICT (9 edge prompts)
- Routing 9/9 class-appropriate; homonym/picker 9/9 correct — incl. the DG-03 'Jackson'
  wrong-asset trap (named asset mfm302 = 0 rows, genuinely dead; pipeline offers both,
  does NOT pass DG-3 MFM's live rows off as the Jackson answer). Zero fabrication/NaN/seed.
- 2 DEFECTS: (1) 'power quality for a spare feeder' → 180 candidates across 14 classes
  (precision broken; 'spare' token bypassed class filter) [validate]; (2) AHU-5 43/45 false
  honest-blank of LIVE voltage_unbalance_pct / max-gap / current_max_spread — reproduces
  the page06 Family-D missing-derivation-binding, no per-leaf reason [validate/ems_exec].

### (5) EXPLICIT VERDICT — CONTRACT **NOT CERTIFIED**
The frames=payloads gate, renderer coverage, and class-correct routing (17/18 pages) PASS,
and 5 pages (07,08,11,12,13) fully meet the contract (payload-direct, real-or-honest-blank
+reason, zero fabrication). But the contract requires EVERY card on ALL 18 pages to comply,
and 33/70 cards fail on strict-DEFECT grounds (not honest-gap, not infra, not nameplate-open):

BLOCKERS (strictly DEFECT — must fix to certify):
- Family A (neg-kw denorm): 49,57,58,59,56 — real load/PF zeroed or blanked [ems_exec/validate]
- Family B (surviving seeds): 66,69,52,54,55,57,18,19,20,21,22,23,25,16 — fabrication,
  contract-(d) [ems_exec/validate] (16 also leaks 'Apr-15..21' seed dates)
- Family C (fab-by-zero full verdict): 10,11,13,14,15,17,74 — 0.0/empty as real, contract-(c)/(d) [ems_exec/validate]
- Family D (false honest-blank of LIVE cols): 43,45 (+ cross-class AHU-5) [validate]
- Family E (misroute): page14 tap-rtcc→thermal-life silent swap [layer1a]
- Family F (legend-leak wrong units): 76 on pages 14+15 [ems_exec/validate]
- Cross-class precision: 'spare feeder' 180-candidate over-recall [validate]

HONEST-GAP (PASS — telemetry, NOT blockers): all reasoned '—' leaves on 05/06(44)/07/08/
11/12/13/16/26/27/48, vThd (thd_voltage_* empty), battery/fuel/thermal/engine columns
genuinely absent, DG idle (power=0), frozen energy counter, panel members with 0-row tables.
INFRA: none (both :8770 and :5433 OPEN throughout).
KNOWN-OPEN[nameplate]: asset_nameplate still holds class_default fabricated ratings elsewhere
(the 20000-vs-160 seeder bug per project memory) — NOT re-triggered here (DG-1 correctly
source='none'; UPS-11 correctly 600 from cmd_equipment_table) but remains the standing
re-seed item; DG-1 seeds 66/69 are a SEPARATE fill-side defect (Family B), not nameplate.

BOTTOM LINE: NOT CERTIFIED. Certification is blocked by 33 DEFECT cards across 6 families
(A neg-kw, B seeds, C fab-by-zero, D false-blank, E misroute, F legend-leak) + 1 cross-class
precision defect. Fix priority per project rule = prompts/context(C,E) → DB derivation-bindings
(A,D) → generic capability(B seed-strip strings+stripped-0.0, F kW/kVA→% normalize). Once
those are green, the payload-direct render path + routing + honest-blank machinery are already
contract-grade (proven by the 5 fully-clean pages + all honest-gap leaves).

## PREFLIGHT RE-RUN 2026-07-04 (3 read-only gates)
GATE 1 HEALTH+INFRA: /api/health -> {"ok":true} PASS. :5433 probe OPEN (ground-truth reachable, not infra_down).
GATE 2 FRAMES=PAYLOADS: CLEAN. grep of fill/**/card-*.tsx + view-model/date-wiring helpers for
  map*SocketToSnapshot / map*ToFrame / assetPageSocket / build*ViewModel( fed a real payload:
  - All *SocketToSnapshot / *ToFrame / assetPageSocket hits are COMMENTS or `import type {ChartFilterParams}`
    (TYPE-only, erased at compile) — zero runtime mapper call.
  - All 5 build*ViewModel() calls (dg-operations-runtime, transformer-tap-rtcc, dg-fuel-efficiency,
    dg-engine-cooling, transformer-thermal-life) are fed a typed-EMPTY scaffold/frame (all-zero snapshot,
    []/1-placeholder series) to produce the CMD V2 tab's OWN empty-state chrome; the REAL data reads
    payload.<slice> DIRECT as vm= and overlays (sanctioned pattern). ems_backend retired.
  => NO offending file:card. Payload renders direct.
GATE 3 RENDERER COVERAGE: CLEAN. 18 routable_pages, 70 unique card_ids (page_layout_cards).
  70/70 resolve: SPECIAL{8,28,60} + COMPONENTS{58 ids} + COMPOSE{5,6,160} + FILL{12 barrels}.
  MISSING renderer: NONE. DUP card_id across fill barrels: NONE.
  COMPONENTS∩FILL overlap on 36 ids is by-design (registry order COMPONENTS[tier2] wins; FILL[tier4]=empty-scaffold
  last-resort for same id) — deterministic, not a duplicate-renderer defect.

## [batch5] Page 13 — 'dg operations and runtime for DG-1'
- routed: diesel-generator-asset-dashboard/operations-runtime (EXPECTED, class-appropriate DG page). routed_ok=true
- asset: asset_pending -> two DG candidates (mfm_id=2 DG-1 MFM has_data; mfm_id=300 GIC-28-N1-DG-01 no data). Re-POST pinned asset_id=2 (class-matched DG-1). n_columns=33. GOOD (class-appropriate pin).
- neuract ground-truth (target_version1.neuract.dg_1_mfm, 35 cols):
  - reactive_energy_import_kvarh ABSENT -> "not measured" HONEST (cards 72). OK.
  - active_energy_import_kwh PRESENT but 44875 rows, 1 DISTINCT value = 27727.707 (FROZEN register); active_power/reactive_power = 0 (DG idle). Honest-blank of energy-delta DEFENSIBLE; "below valid range" reason imprecise but non-fabricating.
- cards 4:
  - 70 Live Operations & Runtime: OK/honest_gap. partial, power=0, availability="—" w/ reason. no NaN/seed.
  - 71 Runtime & Duty: DEFECT — average-load value="—" (honest) BUT sub="peak 77%" SURVIVING SEED (77 = peak of DEFAULT loadPct series in card_payloads; not recomputed/cleared). layer=ems_exec/validate (leaf-blank must clear derived caption). Also OK-ish real 0.0 run-hours.
  - 72 Energy & Reliability: DEFECT — apparentMvah=27.73 = frozen/garbage active_energy register (27727.707/1000) surfaced as live value while activeMwh=0.0/reactiveMvarh=0.0; MTBF/MTTR render 0.0 though note says "left blank" (0.0 reads as real). layer=ems_exec/validate (garbage register leaked to apparent).
  - 73 Power Energy Analysis: DEFECT — payload_error="no default payload + empty exact_metadata"; has_payload=false; WHOLE-CARD blank (render.verdict honest_blank) due to "no default payload in card_payloads for this card+page" = catalog-coverage gap -> contract-b fail (no real component render). layer=layer2/card_payloads.
- cards_ok: 1/4 (card 70). honest_gaps: 70,71,72 (partial with reasons). infra_down=false

---
## ADV SWEEP batch3 — 2026-07-05

### Page 07 | 'real time monitoring for GIC-01-N3-UPS-01'
- routed: individual-feeder-meter-shell/real-time-monitoring == expected. routed_ok=TRUE.
- asset: AI-resolved GIC-01-N3-UPS-01 CL:600KVA (mfm_id 11, class UPS, table gic_01_n3_ups_01_p1, 51 cols). CLASS-MATCHED (UPS prompt -> UPS asset). NO asset_pending. reconcile note: panel-aggregate route -> individual-feeder because has_feeders=False (correct).
- cards 3/3 ok. All fill_source=ems_exec, conforms=True, no payload_error.
  - 36 Power&Energy: verdict partial. Real activeP 198.7kW(=|neuract -202.25avg|, sign-normalized to load-positive), apparentP 199.4kVA, reactiveP 9.9kVAR, real dataSeries. HONEST BLANK '—' x2: reactiveEnergy (today-delta of reactive_energy_import=21985 flat -> 0 movement today, reason denorm_garbage), projectedDemand (NO demand column exists in table). Both defensible honest_gaps.
  - 37 Voltage Monitor: 3 real phase series ~230-240V (neuract voltage_avg 236.03 -> card avg 236.43 MATCH). metrics/legend real. 0 blanks/NaN. verdict partial = 5 undeclared structural leaves, not data gaps.
  - 38 Current Monitor: 3 real phase series 253-299A (neuract current_b/r/y 278/269A MATCH). avg 281A neutral 16.6A. 0 blanks/NaN. Minor cosmetic: yTicks 80-130 don't span ~280A data (axis artifact, not data defect).
- defects: NONE. honest_gaps: card36 reactiveEnergy, card36 projectedDemand.

## ADVERSARIAL SWEEP batch1 2026-07-05 (READ-ONLY; :8770 + :5433 both OPEN)
### 01 | 'real time monitoring for PCC Panel 1'
ROUTED panel-overview-shell/real-time-monitoring  == expected  => routed_ok TRUE
ASSET PCC-Panel-1 mfm_id=317 class=Panel has_data=true has_feeders=true how=AI (class-appropriate; a Panel prompt landed a Panel shell).
GROUND-TRUTH neuract: pcc_panel_1_feedbacks = 35-col BREAKER/RELAY table (ACB on/trip fb, winding temps), 0 ROWS, NO power cols.
  => card-7 rail honest-blank "active_power_total_kw not logged by this meter" is TRUTHFUL (panel own-meter). NOT false-blank.
  Feeder members = GIC-15 PCC-01/02 meters (gic_15_n3/n4_..._se): 24k rows, max_ts today, HAVE active_power_total_kw => real feeder power exists.
CARDS 8 total:
  7   rail-header  partial  real=33/44  seed=0 NaN=no perr=no  honest-blank(3 leaves: no power col / rated cap unknown / vll not measured on panel meter) => honest_gap OK
  5   heatmap      partial  real=34/102 seed=0 NaN=no perr=YES(llm emit timeout ~32558 tok)  => DEFECT[layer2/emit]: AI emit unavailable, default metadata shown; data leaves honest-blank; NO fabrication but functional emit-layer failure (known 32K-tok fail-fast). coverage widgets reporting=4/8.
  160 footer(nav_index chrome)  honest_blank real=0/1  => chrome renders; time-bucket leaf blank (panel own-table empty) reason given => honest_gap OK
  6   scrubber(nav_index chrome) honest_blank real=0/1  => chrome renders; same => honest_gap OK
  8   AI summary(narrative_ai)   render full real=0/0  => renders OK
  9   total consumption  partial real=2/4  seed=0 => honest_gap OK
  10  consumption trend  partial real=1/5  seed=0 => honest_gap OK
  11  quick stats        partial real=3/6  seed=0 => honest_gap OK
DEFECTS: card5 payload_error emit-timeout (layer2/emit). No seed/NaN/fabrication anywhere (seed=0 all cards). INFRA none.

## ADVERSARIAL SWEEP batch 4 (2026-07-05) — pages 10/11/12 (DG-1 asset dashboard)
INFRA: :8770 HTTP ok (/api/health {ok:true}); neuract :5433 OPEN (target_version1/neuract). NOT infra_down.
GROUND-TRUTH: neuract.dg_1_mfm has 44,889 rows but voltage_ll_avg/current_avg/active_power_total_kw are
  ZERO across the ENTIRE table (nonzero count = 0). => DG-1 genset is genuinely idle/off. All 0.0 leaves =
  REAL honest-zero (NOT a fill bug). asset_nameplate dg_1_mfm: rated_kva='' (EMPTY), nominal_voltage_ll=415.0,
  source='none' => any rated_current/kVA-derived value is UNDERIVABLE; nominal is 415 V (NOT 11 kV).

### PAGE 10 | 'dg voltage and current for DG-1' -> diesel-generator-asset-dashboard/voltage-current  ROUTED_OK
  asset: 1b ambiguous (DG-1 MFM mfm_id=2 has_data=true | GIC-28-N1-DG-01 mfm_id=300 has_data=false) — both class DG;
  re-POST asset_id=2 (name-exact, has_data) -> pinned DG-1 MFM. 4 cards 66/67/68/69, all payload-direct, no payload_error.
  DEFECTS:
   - card66 Voltage Live Health [ems_exec/validate]: summary.nominal='11.0' kV = surviving Storybook seed;
     REAL DG-1 nominal = 415 V (contract-d fabrication + wrong voltage class). status.label='Normal' on a
     dead/off genset (all phases 0 V) = surviving seed status misrepresenting idle as healthy (contract-c/d).
   - card67 Voltage History [ems_exec/validate]: stats[2] 'Primary Event'='Motor start sag' surviving seed
     narrative w/ zero events + empty xLabels (contract-d). (real 0.0 + Max-Deviation '—' honest-blank OK.)
   - card68 Current Live Health [ems_exec/validate]: status.label='Normal' on 0-A dead genset = seed status (contract-c/d).
   - card69 Current History [ems_exec/validate]: maxLine 'Rated: 131A'/value 131 = fabricated rating; DG-1
     rated_kva EMPTY/source='none' => UNDERIVABLE (contract-d). Pipeline itself reports 'Rated capacity unknown' on card67.
  HONEST-GAPS (PASS): card66 Unbalance/Spread '—'; card67 Max Deviation '—' (no_nameplate) + worstPeak denorm-guard;
    card68 Unbalance '—'; card69 Max Unbalance '—'; all 0.0 voltage/current/power leaves (REAL idle-genset zero).

## ADVERSARIAL SWEEP batch2 2026-07-05 (pages 04/05/06)
### PAGE 04 | 'harmonics and power quality for PCC Panel 1'
ROUTED: panel-overview-shell/harmonics-pq (== expected). routed_ok=TRUE. Asset PCC-Panel-1
  (mfm_id 317, class Panel, has_data, has_feeders) — class-appropriate, no asset_pending. 5 cards 23-27.
DEFECTS (contract-d fabrication, surviving Storybook seed identity/narrative strings):
 - card 23 (PQ Issues KPI Strip): stats.worst = {id:'ups-05',panel:'UPS-05',table:'MFM_034',
   driver:'5th harmonic current distortion',status:'danger',driverKey:'H5'} with ALL numerics zeroed.
   MFM_034 does NOT exist in registry_lt_mfm; UPS-05(id24)=GIC-02-N6 feeder, NOT a PCC-Panel-1 member.
   Numbers zeroed (honest-blank works) but seed id/table/driver/status STRINGS survived -> fabricated
   worst-offender identity+danger narrative. [ems_exec/validate] Family B. (worstIThd IS real: gic_01_n3_ups_01_p1 iThd 6.07.)
 - card 25 (AI Summary): WHOLE default seed roster survived — period.panels[0..]=UPS-01..05 on
   MFM_025..MFM_034 (none exist / not panel members) + worst/worstVThd/worstIThd all seed ids +
   driver 'H5' + status danger/warning. leaf_stats real:0 (AI-summary data never filled) yet the
   fabricated panel roster+narrative renders. Large seed leak. [ems_exec/validate] Family B.
CARD 24 (Timeline): payload_error='llm call failed (timeout ~25890 tok)' + conforms:False BUT data
  filled REAL (real:192; period.panels = real GIC-01 feeders gic_01_n3/n4/n5/n8, real amps/vAvg/iUnbalance;
  25 hourly points real). Metadata=default fallback, NO seed strings found. Known emit-timeout (no-retry).
  payload_error present -> contract-(e) blemish, but renders real data -> treat ok w/ note, NOT a fab defect.
CARDS 26 (Feeder PQ table, real:32) + 27 (Signature radar, real:32): CLEAN, no surviving seed id-strings.
HONEST-GAPS (PASS telemetry): vThd/worstVThd null on card23/25 — CROSS-CHECKED target_version1.neuract
  gic_01_n3_ups_01_p1: thd_voltage_{r,y,b}_pct = 0 nonzero/53229 (genuinely empty) while thd_current_*_pct
  = 53228/53229 live -> vThd honest-blank CORRECT, iThd real CORRECT. Machinery validated.
INFRA: none (:8770 + :5433/target_version1 OPEN).

## [batch5] Page 14 — 'transformer tap and rtcc for Transformer-01'
- routed: transformer-asset-dashboard/tap-rtcc (EXPECTED, class-appropriate Transformer page). routed_ok=true
- asset: asset_pending -> 3 Transformer candidates. Re-POST pinned asset_id=171 = "GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]" (name+class matched Transformer-01, has_data). GOOD.
- neuract ground-truth (gic_15_n3_pcc_01_transformer_01_se, 70 cols):
  - NO tap/rtcc columns exist -> cards 78/80/81 honest-blank "tap_position/tap_optimal/tap_range/tap_count/ts not measured" is HONEST+correct (energy MFM has no tap-changer register). OK honest degrade.
  - voltage_r_n range 6382.7–6588.45 -> card 79 series 6383–6541 REAL. sag_event_active/swell_event_active columns DO exist.
- cards 4:
  - 78 Tap Position Optimization: OK/honest_gap. honest_blank, all tap kpis null w/ per-leaf reason. no NaN/seed.
  - 79 Voltage Regulation Timeline: DEFECT — voltage series REAL, but events[] (12 entries idx7/15/24 R/Y/B phase) + stat "Primary Event: Motor start sag" are SURVIVING CROSS-CARD SEEDS: they originate from card_payloads card_id=44 page individual-feeder-meter-shell/voltage-current (card 79's OWN default has events=null). Render gap DECLARES history.data.events "not measured" yet payload carries 12 fabricated events -> internal contradiction + contract-d fabrication. layer=ems_exec/emit (fill pulled base-component Storybook defaults, not card-79 empty default). NOTE: sag/swell_event_active cols EXIST so events were derivable — secondary under-coverage.
  - 80 Recent Tap Changes: OK/honest_gap. honest_blank, rows=[] w/ per-leaf reason (ts/tap_position absent). no seed.
  - 81 Tap Activity & Wear: OK/honest_gap. honest_blank, all tap-count kpis "—" w/ reason. no seed.
- cards_ok: 3/4 (78,80,81). DEFECT: 79. honest_gaps: 78,80,81. infra_down=false

## ADVERSARIAL SWEEP BATCH 6 (pages 16-18, UPS asset GIC-01-N3-UPS-01, mfm_id=11) 2026-07-05
INFRA: :8770 up (health ok), :5433 OPEN throughout. NOT infra_down.
ASSET RESOLUTION: all 3 prompts -> UPS mfm_id 11 (GIC-01-N3-UPS-01 CL:600KVA), class UPS via AI,
  no candidate list (confident pin), CLASS-APPROPRIATE. Ground-truth table gic_01_n3_ups_01_p1
  = 72 cols, 53,220 rows, latest ts 2026-07-05 (LIVE). Real: voltage_avg 225-240V, voltage_ll 390-416,
  current_avg 0-336A, apparent_power_total_kva 0-230 (last-24h avg 195.6), active_power_total_kw NEGATIVE
  (-227..0, sign convention), power_factor -0.999..1, frequency 49.5-50.7Hz. NO transfer/mode/bypass/
  battery/SOC/temperature column exists.

PAGE 16 ups-asset-dashboard/battery-autonomy (4 cards 50-53): routed_ok. No swaps, no payload_error, all fill_ok.
  - card 50 Battery Health: honest_blank. SOC/Temperature blanks LEGIT (no such cols). BUT "Output Voltage
    not measured by this meter." + "Output Current not measured by this meter." are FALSE-BLANKS — voltage_avg
    (225-240V) + current_avg (0-336A) HAVE 53,220 live rows. => [ems_exec/validate] false-blank DEFECT (Family D).
  - card 51 Battery Health History: honest_blank. Score sub-series legit blank. DEFECT: annotation leaf
    .batteryHistory.peak.label = 'peak temp 35°C' is the SURVIVING Storybook DEFAULT seed (card_payloads.51
    contains "peak temp 35C" verbatim) — leaks fabricated 35C peak while data blanked. => [layer2/emit] seed-leak (Family B/F).
  - card 52 Backup Readiness / card 53 Backup Readiness History: partial per loop-note but payload value
    leaves all '—'/0.0 (autonomy/backup SCORES genuinely not meter-measured). HONEST-GAP, ok.
PAGE 17 ups-asset-dashboard/output-load-capacity (3 cards 57-59): routed_ok, validation PASS. No payload_error.
  - card 57 UPS Capacity: partial, all scoreCells '—' unit '/100' (composite readiness SCORES, not raw meter
    leaves). reason 'Sensor reading below valid range' (neg active_power gate). HONEST-GAP defensible.
  - card 58 UPS Load: partial. REAL data flows: scoreCells[0]=203.5 kW (abs of neg DB), pf -0.999. sparkline
    30d loadPct all 0.0 (older days absent; seed 55.4 correctly stripped). ok (honest_gap on empty history).
  - card 59 Composite: partial. kpiCells[0]=235.56 real. DEFECT: .composite.floor.label='Readiness: 70%'
    = SURVIVING default seed (card_payloads.59 contains 'Readiness: 70%') while floor.value blanked to 0. => seed-leak (Family F).
PAGE 18 ups-asset-dashboard/source-transfer (3 cards 54-56): routed_ok, validation PASS. No payload_error.
  - card 54 Transfer readiness: partial, scoreCells '/100' all '—' (readiness SCORES not measured). HONEST-GAP ok.
  - card 55 Activity: partial. DEFECT (severe): count30d / lastTransferDays / lifetimeTransfers / both metrics
    ALL = 232.0 (identical). Defaults were distinct (2/5/15) -> overwritten with ONE bogus number smeared across
    semantically-unrelated leaves. Table has NO transfer/mode column; sag/swell events=0 over 30d. Should be
    honest-blank. => [ems_exec] FABRICATION-by-misbinding DEFECT (Family C).
  - card 56 Composite: partial. REAL: kpiCells Average Input Voltage 236.56 (==last-1h voltage_avg 236.97),
    freq 49.9 (==49.88). Bypass V 0.0 honest-blank (single-meter, no bypass). DEFECT: .composite.floor.label
    ='Readiness: 70%' = surviving default seed. => seed-leak (Family F).
BATCH-6 DEFECT TALLY: 4 defect cards (50 false-blank; 51,59,56 seed-leak; 55 fabrication) across 6 cards flagged;
  routing+asset+render-path all contract-grade. Cards clean/honest-gap-ok: 52,53,54,57,58.

### Page 08 | 'energy and power for GIC-01-N3-UPS-01'
- routed: individual-feeder-meter-shell/energy-power == expected. routed_ok=TRUE.
- asset: same UPS mfm_id 11, class-matched, no asset_pending, no payload_error on any card.
- cards 4/4 present, all fill_source=ems_exec conforms=True. BUT active/reactive-power history is being zeroed:
  - **DEFECT [ems_exec/validate]**: active_power_total_kw & reactive_power_total_kvar carry REAL live data (neuract hourly buckets ~-203kW / -9.85kVAR, ~149 samples/hr recent). Snapshot cards render them fine (card36 activePower=199kW, card41 hvInputKw=200.7kW via _verify abs()). BUT the HISTORY/bucketed path collapses them to 0.0 and labels "denorm_garbage / Sensor reading below valid range":
    - card 40 Power Energy Analysis: bars[*] ALL {active:0.0,reactive:0.0} (12 bars); yMax/activePowerAvgKw blanked. gap cause=denorm_garbage on active_power_total_kw + reactive_power_total_kvar. Both columns are logged (column_logged=True) so it's a validity-gate rejection, not honest absence. real 26/36.
    - card 42 Load Anomalies: actualLoad[*].value=denorm_garbage(active_power_total_kw), loadFactorPct/yMax=denorm_garbage. real 1/14. (dipEvents=derivation_unbound loadAnomalyEvents — separate honest gap, no binding.)
    - card 41 efficiencyPct leaf: denorm_garbage(active_power_total_kw) while hvInputKw/lvOutputKw from the SAME column rendered 200.7 — INCONSISTENT within one card = confirms gate bug.
  - INCONSISTENCY is the tell: same column, same run, same asset → accepted in snapshot, zeroed/blanked in history/derivations. Live data exists.
- HONEST (not defects): card39 activeEnergyKwh=0.0 (neuract active_energy_import_kwh genuinely all 0.0); card41 lossKwh/deltaPct=column_absent (hv_input_kw/lv_output_kw not on a single UPS meter — legit); card42 dipEvents=derivation_unbound.
- card39 Today's Energy: totalEnergyKwh=232, reactiveEnergyKwh=21986 real; OK.
- routed_ok TRUE; cards_ok = 1/4 (only 39 clean). 40,42 = DEFECT. 41 = MIXED (real hv/lv but efficiencyPct hit by same gate) -> flag defect leaf.

### PAGE 05 | 'voltage and current for PCC Panel 1'
ROUTED: panel-overview-shell/voltage-current (== expected). routed_ok=TRUE. Asset PCC-Panel-1
  (317, Panel, has_data/has_feeders) class-appropriate, no asset_pending. 5 cards 18-22.
DEFECTS (contract-d fabrication, surviving Storybook seeds):
 - card 19 (AI Summary): wholesale default roster survived — worstCurrent(ups-04/MFM_033),
   worstVoltage(ups-05/MFM_034), period.panels[0..]=UPS-01..05 on MFM_025..034. None exist in
   registry_lt_mfm / not PCC-Panel-1 members. [ems_exec/validate] Family B (whole-card seed roster).
 - card 21 (Current Distribution): HYBRID leak — rows have REAL id/panel/amps
   (gic-01-n3-ups-01, amps 287 — matches neuract current_avg range 232-308) BUT seed
   table='MFM_025..' + seed status/causeKey('warning'/'capacitorStep') SURVIVED on those rows
   (voltage metrics zeroed). Internally contradictory: real id + fabricated table + fabricated
   narrative. [ems_exec/validate]. Contrast: cards 20 & 22 (same panels) correctly carry REAL
   table=gic_01_n3_ups_01_p1 — so card 21 uses a buggier fill path than its siblings.
CLEAN: card 18 (Events KPI Strip — no surviving seed numbers/MFM refs), card 20 (Event Timeline —
   real panels+tables+25 hourly points, status computed from real data), card 22 (Other Panels
   Event table — real gic_* tables).
VALIDATE TELEMETRY BLEMISH: all 5 cards render leaf_stats real:0/data:0 + verdict 'render/full'
   despite cards 20/22 clearly carrying real amps/vAvg. leaf_stats undercounts here (validate telemetry
   unreliable) — render is real, but the 'full' verdict is not evidence of coverage. [validate] minor.
INFRA: none.

### PAGE 11 | 'dg engine and cooling for DG-1' -> diesel-generator-asset-dashboard/engine-cooling  ROUTED_OK
  asset: same 1b ambiguous DG pair; re-POST asset_id=2 -> DG-1 MFM (n_columns=34). 3 cards 60/61/62,
  all payload-direct, no payload_error.
  GROUND-TRUTH: dg_1_mfm has ZERO engine/thermal/coolant/oil/rpm/speed/pressure columns (electrical MFM only);
    frequency_hz/power_factor_total/current_avg also 0 across whole table => 'denorm_garbage/below valid range'
    verdict is HONEST. Engine-cooling metrics are genuinely UNMEASURED by this meter.
  card60 Engine 3D Callout Viewer: equipment.id=2 resolved, object=null/viewer={}/template=null (no DG GLB bound).
    leaf_stats all 0, verdict=render. Structural shell, NO fabricated data. validation warn 'no default payload'.
    => OK / honest coverage-gap (3D model not available), NOT a defect.
  DEFECTS:
   - card61 Thermal Timeline [ems_exec/validate]: chart.events survives 2 SEED event markers —
     {title:'Exhaust over-temp',label:'-15h',severity:'danger'} + {title:'Coolant high',label:'-10h',severity:'warn'};
     value zeroed but title/severity/label NARRATIVE survives; view-model.ts:76 passes p.events through -> markers
     RENDER on an all-empty timeline (zero engine telemetry) = fabricated events (contract-d). Same family as p10 'Motor start sag'.
   - card62 Pressure·Speed·Load [ems_exec/validate]: chart.events survives seed marker
     {title:'Oil pressure low',label:'-2h',severity:'warn'} -> renders on empty mech timeline = fabricated event (contract-d).
  HONEST-GAPS (PASS): card61 all temp series empty + Peak-Exhaust/Max-Coolant/Events KPIs '—'; card62 all
    pressure/speed/load series empty + Peak-Load/Avg-Load/Min-Oil-P KPIs '—'; insight blanked (no-fabrication guard).
    All correct honest-blanks for absent engine columns + idle genset. (Only the surviving event-marker titles are the defect.)

## [batch5] Page 15 — 'transformer thermal life for Transformer-01'
- routed: transformer-asset-dashboard/thermal-life (EXPECTED, class-appropriate). routed_ok=true
- asset: asset_pending -> 3 Transformer candidates; pinned asset_id=171 (Transformer-01, has_data). GOOD.
- neuract ground-truth (gic_15_n3_pcc_01_transformer_01_se):
  - NO temperature/oil/winding/hotspot columns -> winding/oil/hotspot honest-blanks HONEST+correct.
  - active_power_total_kw range -1361..-635 (ALL NEGATIVE = reverse/import sign convention = REAL data, not garbage). power_factor_total -0.999..1 REAL. voltage_avg 6373..6561 REAL.
  - ROOT CAUSE: validate mis-flags negative-convention power/pf as "denorm_garbage/below valid range"; downstream math emits absurd values that LEAK into render.
- cards 4:
  - 74 Thermal Life: OK/honest_gap. all temp metrics "—" honest, stressPct null honest, only stressBorderPct=100 (config). No garbage leaked. PASS.
  - 75 Life & Capacity: DEFECT — lifeRemainingYears=10156.7 (default 20.5) = FABRICATION (10,156-yr transformer life from garbage energy math); note claims "derived from energy/power" without disclosing nonsense. layer=ems_exec/validate.
  - 76 Thermal Timeline: DEFECT — legend Load=-855.00006% and Efficiency=-855.00006% (physically impossible, from mis-flagged negative active_power) LEAKED into render despite gap declaring loadPct garbage; tempAxis.max/min = voltage band {216/240/264} injected into a degC axis (wrong-domain config leak). layer=ems_exec/validate.
  - 77 Insulation Aging & Loss of Life: DEFECT (minor) — agingFactor/faa legend show 0.997 while render gap declares faa 'denorm_garbage' (inconsistent surfacing); LoL/deltaLol/lifeUsed honestly null. In-range so low severity. layer=ems_exec/validate.
- cards_ok: 1/4 (74). DEFECTS: 75,76,77. honest_gaps: 74. infra_down=false

### 02 | 'energy and distribution for PCC Panel 1'
ROUTED panel-overview-shell/energy-distribution == expected => routed_ok TRUE. ASSET PCC-Panel-1 317 Panel (class-appropriate).
2 cards, both panel_aggregate consumers/energy_distribution/pcc_panel.py, coverage 4/8 feeders (honest partial).
  12 Energy Input & Distribution  partial real=11/33 seed=0 NaN=no perr=no conforms=T => honest_gap OK (kpi/rail/widgets render)
  13 Energy Flow Diagram(Sankey)  partial real=30/88 seed=0 NaN=no perr=no conforms=T => honest_gap OK (flow.vm renders)
DEFECTS: none. Clean page. INFRA none.

### 03 | 'energy and power for PCC Panel 1'
ROUTED panel-overview-shell/energy-power == expected => routed_ok TRUE. ASSET PCC-Panel-1 317 Panel (class-appropriate).
4 cards, panel_aggregate consumers/energy_power/pcc_panel.py, coverage 4/8 feeders.
  14 Cumulative Energy      partial real=1  seed=0 => CLEAN real values (78,010 kWh active / 1,010 kVArh) + honest-blank — for SEC/target/insight => OK
  15 Today live power       partial real=1  seed=0 => CLEAN real (784.7 kW active / 34.2 kVAr) + honest-blank — for load-factor/worst-peak marker => OK
  16 Energy Consumption Trend partial real=1 seed=0 => UPS energy=0.0 is TRUTHFUL (neuract gic_01_n3_ups_01_p1 active_energy_import_kwh genuinely 0 over 3355 rows — UPS meters register on EXPORT; import=0 real). BPDP 77,970 kWh real. Borderline semantic (import register on an export feeder) but NOT fabrication (matches DB). => honest_gap OK
  17 Daily Power Demand by Feeder partial real=50/79 => POINTS/LEGEND REAL+CORRECT (UPS 558-603kW, BPDP 306-363kW real hourly series; HHF honest-null — matches roster: no HHF member on 317). BUT stats WORST-PEAK=0.0 kW + LOAD-FACTOR=0.0% while own points peak at 603.85kW => DEFECT[ems_exec/fill: fab-by-zero]. Storybook default was "332"/"92"; pipeline OVERWROTE to 0.0 (not surviving seed — zeroed derived stat). Should compute ~603 from points OR honest-blank —. Also stale seed label sub:"at 17" survived. Layer=ems_exec/fill (demand.view.stats leaves have NO fill recipe in roster — only points+legend bound).

GROUND-TRUTH cross-checks done: pcc_panel_1_feedbacks=0 rows/breaker-only (panel own honest-blank truthful); GIC-15 PCC feeders real power+active_power_total_kw fresh today; GIC-01 UPS feeders real power (~157-227kW/unit) but active_energy_import_kwh genuinely 0 (export register). No fabrication except card-17 fab-by-zero stats.
BATCH1 SUMMARY: 3/3 routed_ok. Defects: [01] card5 emit-timeout payload_error (layer2/emit, no fabrication); [03] card17 worst-peak/load-factor fab-by-zero (ems_exec/fill). All other partials = honest per-leaf blanks with reasons. INFRA none (both OPEN throughout).

### PAGE 12 | 'dg fuel efficiency for DG-1' -> diesel-generator-asset-dashboard/fuel-efficiency  ROUTED_OK
  asset: same 1b ambiguous DG pair; re-POST asset_id=2 -> DG-1 MFM. 3 cards 63/64/65, all payload-direct, no payload_error.
  (curl exit 52 transport hiccup but body complete + valid JSON.)
  GROUND-TRUTH: dg_1_mfm has NO fuel/tank/autonomy/run-hour columns. The only fuel feed in neuract is aux_hsd_plc_feedbacks
    (hsd_1/hsd_2_tank_level, SHARED HSD tanks not per-DG) and those are ALSO 0 across the whole table => no live fuel
    data exists for DG-1 anywhere. All 3 cards' validation.verdict='fail' reason='payload needs numeric values but no
    usable numeric column' — HONEST no-data, NOT a render gate (cards still render honest-blank, no whole-card refuse).
  card63 Fuel Tank Anatomy: snapshot autonomy/fuelRate/fuelTemp/fuelLevel/efficiency ALL null; display labels only.
    CLEAN honest-blank, zero fabrication. => OK/honest-gap.
  card64 All Runs (Fuel Log): faults/starts/avgLoad/runHours/totalFuelL null; totalKwh 0.0 (real). CLEAN. => OK/honest-gap.
  DEFECT:
   - card65 Fuel & Tank Composite [ems_exec/validate]: chart.events survives 2 SEED markers {title:'Reserve low',label:'-16h'}
     + {title:'Reserve low',label:'-8h'} on series 'fuelLevel' (a column that doesn't exist); value zeroed but title/label
     narrative survives; view-model.ts:81 arr(p.events,base.events) passes them to render -> fabricated 'Reserve low' fuel
     markers on an empty timeline (contract-d). Same family as p10/p11. (All fuel series/KPIs honest-blank '—', axes/domain
     structural — only the event markers are the defect.)
  HONEST-GAPS (PASS): card63 all snapshot leaves null; card64 all run-log stats null + totalKwh real-0; card65 Efficiency/
    SFC/Load KPIs '—', Cost ₹0.0 (real-zero, no consumption), Level/Rate/Temp series empty, band 0-0.

## BATCH 4 SUMMARY (pages 10/11/12)
ROUTING: 3/3 class-appropriate (all DG prompts -> diesel-generator-asset-dashboard/*; 1b correctly offered ONLY
  DG candidates, never a UPS/Panel; pinned DG-1 MFM via has_data+name-exact). routed_ok all true.
CARDS: 10 total. NO payload_error, NO NaN, all render payload-direct. Real 0.0 = genuine idle-genset zero (verified
  vs neuract: dg_1_mfm all electrical cols 0 across 44,889 rows). Honest-blanks all carry a per-leaf reason.
DEFECTS (5 cards, ALL contract-d surviving-seed, family B/'Motor start sag'):
  p10 c66 nominal='11.0'kV (real 415V) + status='Normal' on dead genset; c67 stats 'Primary Event: Motor start sag';
  c68 status='Normal' on 0A; c69 maxLine 'Rated: 131A' (rated_kva EMPTY/underivable);
  p11 c61 events 'Exhaust over-temp'/'Coolant high'; c62 event 'Oil pressure low';
  p12 c65 events 'Reserve low'×2.
  ROOT CAUSE: fill/*/view-model.ts overlays p.events / seed status / seed nominal / seed rated-line verbatim without
  strip-when-no-data; the numeric neutraliser zeros VALUES but not the narrative TITLE/LABEL/SEVERITY/status/nominal strings.
  Fix priority: generic capability (strip seed event-markers + status + nominal + rated-line when the backing leaf is
  honest-blank/absent) — the same seed-strip gap the prior batch flagged as Family B.
INFRA: none (both :8770 and :5433 OPEN throughout).

### PAGE 06 | 'voltage and current for GIC-01-N3-UPS-01'
ROUTED: individual-feeder-meter-shell/voltage-current (== expected). routed_ok=TRUE. Asset bound
  DIRECTLY by AI to GIC-01-N3-UPS-01 CL:600KVA (mfm_id 11, class UPS, table gic_01_n3_ups_01_p1,
  has_data) — class-appropriate, NO asset_pending, no cross-class candidate. 4 cards 43-46.
DEFECTS:
 - card 43 (Voltage Live Health): FALSE honest-blanks. Blanks voltageUnbalancePct + voltageMaxMinGap
   with reason 'no derivation binding configured'. CROSS-CHECK target_version1.neuract gic_01_n3_ups_01_p1:
   voltage_unbalance_pct = 53248/53248 LIVE; voltage_max & voltage_min = 53249/53249 LIVE (gap trivially
   computable). derivation_binding has ZERO rows for these -> config gap SUPPRESSES available live data.
   Reason present but data IS measured -> [validate/derivation_binding] defect (Family D), NOT acceptable gap.
 - card 45 (Current Live Health): FALSE honest-blank. Blanks max_gap 'no derivation binding for
   current_spread_br'. CROSS-CHECK: current_spread_br = 53247/53248 LIVE. Same class as card43. [validate/derivation_binding].
 - card 44 (Voltage History): real R/Y/B phase series (228-240V L-N, real:109) + real stats
   (nominal 240 correct L-N) BUT maxLine=430/minLine=410/expectedMax/Min=430/410 = SURVIVING SEED band
   on WRONG unit scale (line-to-line ~415-430 band drawn over line-to-neutral 228-240 data; band sits
   far above all real points). band_policy has NO 410/430 edges (voltage band = deviation-% 1,2,3,5) ->
   410/430 is frozen seed, not config-derived. [ems_exec/validate] fabrication + unit-mismatch (Family F).
CLEAN: card 46 (Current History) — real:115, verdict render/full, no surviving seeds.
HONEST-GAPS (PASS telemetry): card43 'ts not measured by this meter' (timestamp leaf) + card44
  'sensor reading below valid range -> no reading' (per-point clamp) are legit per-leaf gaps.
INFRA: none. Asset-resolution + payload-direct render path CLEAN on this page; defects are
  data-binding (D) + seed-band (F), consistent with prior families.

### Page 09 | 'power quality for GIC-01-N3-UPS-01'
- routed: individual-feeder-meter-shell/power-quality == expected. routed_ok=TRUE. asset same UPS, class-matched, no asset_pending, no payload_error, seed:0 all cards.
- **DEFECT [layer2/emit] card 47 Power Quality — semantic mis-binding (fabrication-of-meaning):** the true source cols are 100% NULL over 20k rows (thd_voltage_r/y/b_pct, harmonic_5th_pct, harmonic_7th_pct, thd_compliance_v_avg all 0 non-null). Rather than honest-blank, data_instructions rebind the slots to CURRENT-THD columns:
    - snapshot.vThd.valuePct=6.1 <- thd_current_b_pct (CURRENT-B distortion shown as VOLTAGE-THD)
    - snapshot.h5.valuePct=8.9 <- thd_current_r_pct (current-R shown as 5th-harmonic)
    - snapshot.h7.valuePct=7.7 <- thd_current_y_pct (current-Y shown as 7th-harmonic)
    - snapshot.iThd.valuePct=7.567 <- thd_compliance_i_avg (CORRECT). 
  Card claims verdict 'render', leaf_stats real 4/4, validation 'pass' — but 3/4 tiles are real numbers on WRONG semantic columns. Values are NOT surviving seeds (seed vThd=4,h5=10.4,h7=5.3 differ) and NOT the null source cols. Honest behavior = '—' + 'not measured by this meter' (as card 48 correctly did). SERIOUS: passes as real, misleads.
- card 48 Distortion & Harmonic Profile: CORRECT. i-thd view real (R·THD 6-8.5% matches thd_current_r max 11.9%). v-thd series HONEST BLANK structurally_null (thd_voltage_* genuinely 100% NULL). 0 blanks-as-—, 0 NaN, seed 0. PASS w/ honest_gaps.
- card 49 Load Impact & Transformer Stress: k-stress series real (6-8.9%, current-THD proxy), pf-health real (pf -0.999/0.995). K-factor col_absent (legit honest — no k-factor col). stats[1] gap denorm_garbage(active_power_total_kw) = SAME [ems_exec/validate] gate as page08 (active power live but rejected as below-range) — but the visible stat rendered 8.9 so mostly OK; flag the leaf. 0 blanks-as-—, 0 NaN.
- routed_ok TRUE. cards_ok: 48 clean(honest gaps), 49 mostly-ok(1 gate leaf), 47 DEFECT(semantic mis-bind).

### CANONICAL RE-READ CORRECTION (batch2)
Page 04 initial file was an INTERIM write (bg curl); CANONICAL final run r_a68ae6e694 (152s, notes loop1:[])
  => card 24 (Timeline) AI-emit SUCCEEDED: conforms True, payload_error None, 0 seed strings, real data.
  card 24 is CLEAN (NOT a timeout defect). Cards 23 (worst.id/panel/table=ups-05/UPS-05/MFM_034) and
  25 (32-string UPS/MFM roster) seed leaks PERSIST in canonical file — defects stand.
Page 05 canonical r_b57a82feb3, Page 06 canonical r_aea5abb769 — single-curl, not overwritten; all
  seed findings confirmed (p05 card19=29str, card21=8str; p06 card44=430/410 band).

## BATCH2 VERDICT (pages 04/05/06): NOT CLEAN
Routing PERFECT on all 3 (each landed class-appropriate shell; page06 UPS bound directly, no cross-class).
Payload-direct render path works. 6 DEFECT cards:
  04: card23 (seed worst-offender identity MFM_034/UPS-05 + danger narrative), card25 (whole seed roster)
  05: card19 (whole seed roster), card21 (seed table MFM_0xx + seed status/cause on real-id rows)
  06: card43+45 (FALSE honest-blanks of LIVE neuract cols voltage_unbalance_pct/voltage_max-min/current_spread_br
      via missing derivation_binding), card44 (seed voltage band 430/410 on wrong L-N unit scale)
Clean: 04(24,26,27) 05(18,20,22) 06(46). Families: B(seed strings) on 23/25/19/21, D(false-blank) on 43/45,
F(seed band/unit) on 44 — all consistent with the standing batch-1 family taxonomy.

================================================================================
## PREFLIGHT — FRESH RE-HOST VERIFICATION — 2026-07-05 (READ-ONLY, 4 gates)
## host :8770 = freshly-rehosted FIXED pipeline (seedless payload_stripped, zero
## runtime strip_to_placeholders, honest-blank null_scalar import fixed, canonical
## lt_mfm.id, ONE pre-Layer-2 validation, payload-direct FE, dead code purged)
================================================================================

### GATE 1 — liveness / freshness — PASS
- GET /api/health -> {"ok": true, "sb_base": "http://100.90.185.31:6008"} (ok).
- :5433 probe -> OPEN (neuract ground-truth reachable; a blank here = real gap, NOT infra_down).
- outputs/logs/ -> present, EMPTY (0 per-run jsonl) => FRESH; pipeline_/ai_/failures_<run_id>.jsonl
  accumulate here as the sweep runs. outputs/fullsweep_unknown/host.log not yet present (no runs).
- outputs/fullsweep_unknown/pages/ ensured (durability sink for v18_<nn>.json).

### GATE 2 — FRAMES=PAYLOADS (no card routes payload THROUGH a socket/frame mapper) — CLEAN
Grep of every host/web/src/cmd/fill/**/*.tsx + view-model/date-wiring/helpers for
map*SocketToSnapshot / map*ToFrame / snapshotFromFrame / assetPageSocket / build*ViewModel( fed a payload:
- ZERO executable calls to any *SocketToSnapshot / *ToFrame / snapshotFromFrame (grep of non-comment
  call-sites returned empty).
- Every map*ToFrame / assetPageSocket / mapPanel*AggregateToSnapshot hit is (a) a CODE COMMENT documenting
  the DELETED live path, or (b) `import type { ChartFilterParams } from "@cmd-v2/realtime/assetPageSocket"`
  (TYPE-only, erased at compile — no runtime coupling).
- Every build*ViewModel(...) call is fed a LOCAL typed-EMPTY scaffold — emptyEngineFrame(), emptyFuelFrame(),
  emptyScaffoldFrame() (1-bucket zero TapRtccFrame), dg-operations emptyVm()'s {snapshot:emptyOpsSnapshot(),
  buckets:[],count:0}, thermal {variant:'lt',snapshot(all-0),timeline:[{slot:'—',...}],aging} — a CMD V2
  typed-empty BASE the Layer-2 payload overlays. NOT an ems_backend socket/frame. Sanctioned pattern.
- renderCmd (registry.tsx) resolution keys render_card_id??card_id and routes payload DIRECT:
  SPECIAL(envelope) -> envelope-detect -> COMPONENTS (`<Comp {...unwrap(p0)}/>` = PRIMARY) -> COMPOSE -> FILL
  -> HonestBlank. The `frame` arg is passed but the FILL view-models IGNORE it. PAYLOAD-DIRECT confirmed.
- VERDICT: CLEAN. No offending file:card. ems_backend fully retired from the render path.

### GATE 3 — RENDERER coverage (18 routable pages) — PASS
- routable_pages = 18 enabled. page_layout_cards -> 70 distinct card_ids required across them.
- Renderer union (keyed by render_card_id??card_id, resolution order SPECIAL>envelope>COMPONENTS>COMPOSE>FILL):
    SPECIAL   {8,28,60}                       (narrative_ai + asset_3d ComingSoon envelopes)
    COMPONENTS {7,9,10..27,36..59,66..72,74..81}  (58 ids — PRIMARY direct-render path)
    COMPOSE   {5,6,160}                       (card-5 heatmap stack + RTM chrome atoms)
    FILL/*.tsx glob = 43 ids                  (last-resort view-model path; 12 barrels)
- MISSING (required, NO renderer in ANY map): NONE (70/70 resolve).
- DUP FILL card_id across barrels: NONE (43 distinct keys; loader warns on collision, 0 fired).
- FILL∩COMPONENTS overlaps (18-27,36-49,66-69,74-81) are NOT conflicts — COMPONENTS wins in renderCmd order;
  FILL is the documented fallback, uniquely needed only for 61-65,71,73 (DG engine/fuel/ops, no COMPONENTS entry).
- UPS 50-59 have NO fill barrel — correctly served by COMPONENTS. panel-RTM 5,6,160 -> COMPOSE. card 60 -> SPECIAL.
- VERDICT: CLEAN. Full renderer coverage, no duplicates.

### GATE 4 — /api/frame contract (per-card date re-fetch) — DOCUMENTED
host/server.py do_POST /api/frame (line 569); window via _date_window_for(consumer,date_window) (line 317).
REQUEST (JSON):
  exact_metadata   (or payload if dict)                         REQUIRED (400 if missing)
  data_instructions (obj; .consumer drives endpoint+window)     default {}
  asset_table      (or consumer.asset_table)                    REQUIRED (400 if missing)
  consumer         (or data_instructions.consumer; .endpoint)
  date_window      (FE date-control window)                     -> _date_window_for
  _default_payload (harvested default, for honest strip on error)
RESPONSE: {ok:true, why:"ok", endpoint, payload}  — payload = re-filled CMD_V2 payload via ems_exec.run_card
  (db_link=neuract dsn), then display_dash.apply at serve boundary + roster_stats stripped (telemetry key
  never rides to FE). Error -> 500 {ok:false,error} (traceback printed); honest-degrade still returns a
  stripped shape-complete payload (no seed leak). missing exact_metadata|asset_table -> 400.

### PREFLIGHT VERDICT: 4/4 gates GREEN. Ready for the 18-page sweep.

## Batch 2 — verifier (pages 07-12)

### Page 07 | 'real time monitoring for GIC-01-N3-UPS-01' | run_id r_82157379cd
- routed: individual-feeder-meter-shell/real-time-monitoring — MATCHES expected. routed_ok=TRUE.
- 1a first proposed panel-overview-shell/RTM (8 cards) → granularity_reconcile dropped to individual-feeder-meter-shell (has_feeders=False) → 3 cards. Correct (single UPS asset, no feeders).
- asset: 1b pinned GIC-01-N3-UPS-01 mfm_id=11 table gic_01_n3_ups_01_p1, class UPS, how=AI, no class_mismatch. CORRECT.
- cards 36/37/38 all fill_source=ems_exec, fill_ok=True, no payload_error, no NaN/null, variant=baseline.
- card 36 (Power&Energy): activePower 192 kW, apparentPower 193 kVA (real, matches neuract active_power_total_kw≈-192 abs). activeEnergy=231 via todaysEnergyTotalKwh DEAD-COUNTER FALLBACK (active_energy_import_kwh flat 0 → integrates power series → real_approx "integrated from power", NOT fabrication — verified energy.py:30-42).
  - HONEST-BLANK reactiveEnergy='—': reactive_energy_today_kvarh window delta unobservable over 30s live window (register flat) → _pick_register None → '—'. NEVER a fabricated zero. Correct (energy.py:127-129).
  - HONEST-BLANK projectedDemand='—': worstPeakKw _series found no active_power_total_kw rows in derived-scope ctx → None. Peak IS observable in dataSeries so this is a fillable-but-blanked honest_gap (minor); no fabrication. (power.py:27-30)
- card 37 (Voltage): 3 phase series ~230-240 V real. OK.
- card 38 (Current): 3 phase series ~260-298 A real. OK.
- NOTE (non-defect): freshness.tone='fail' + lastUpdateLabel='Last update —' = byte-identical Storybook seed chrome (metadata leaf, frontend fills live clock); cosmetic, not a data fabrication.
- VERDICT: 3/3 cards ok. honest_gaps: reactiveEnergy, projectedDemand (card 36). defects: none. infra_down=false.

---
## Batch3 Page 13 — 'dg operations and runtime for DG-1'  (run_id r_44796d791a)
- routed: diesel-generator-asset-dashboard/operations-runtime == expected → ROUTED_OK
- asset: DG-1 MFM (mfm_id 2, class DG). asset_pending→re-POST asset_id=2 (both candidates class DG, DG-1 MFM has_data=true → clear class match). 33 basket cols.
- neuract ground truth (target_version1.neuract.dg_1_mfm, 45450 rows): over the card 24h window active_power_total_kw FLAT 0, active_energy_import_kwh FLAT 27727.707 (min==max across 17241 rows) → DG genuinely IDLE, real data present but zero/flat. reactive_energy_import_kvarh col ABSENT (card72 honest-blank correct); reactive_power_total_kvar present.
- cards 4/4 render, no payload_error, no NaN.
- DEFECT (card 71 Runtime & Duty): seed literal "sub":"peak 77%" SURVIVES in cmd_catalog.card_payloads.payload_stripped (verified: 'peak 77%' in stripped default = True) and leaks to served card (value honest-blanked to '—' but sub caption kept fabricated 'peak 77%'). Layer [card_payloads/strip]; surfaced via llm_timeout degrade (card71 AI emit failed → default payload verbatim). Contradicts "seedless payload_stripped, ZERO runtime strip" host claim.
- HONEST-GAP + reason-fidelity issue (cards 70,71,73): idle-zero real data (0 kW) blanked with denorm_garbage reason "Sensor reading below valid range — treated as no reading" — mischaracterizes valid idle-zero as sensor-fault. reason_template has NO idle-zero cause; single denorm_garbage template. Layer [ems_exec/fill]. Leaves pass render contract (blank+reason) but reason wording fabricates a fault narrative.
  - card70: 1 gap liveOps.service.fraction (loadFactorPct on 0kW). verdict partial, real 9/14.
  - card71: 4 gaps (duty labels column_absent + runHours/loadPct/topKpi denorm_garbage). verdict partial, real 2/8. + llm_timeout fallback.
  - card72: 1 gap energyReliability.cells[1] reactive_energy col_absent (CORRECT — col truly missing). verdict partial real 4/9.
  - card73: fully honest_blank (real 0/7) — all 3 series denorm_garbage (flat-0 energy/power) + data.labels col_absent. Defensible blank (nothing non-zero to plot) but same fault-narrative reason issue.

## BATCH1 v18_01 — 'real time monitoring for PCC Panel 1' — run_id r_f9787f915f
routed=panel-overview-shell/real-time-monitoring (EXPECTED, verbatim) — routed_ok=TRUE
asset=PCC-Panel-1 mfm_id=317 how=AI class_prior=Panel (PASS). Panel own-table pcc_panel_1_feedbacks=breaker/relay FB, 0 rows, NO power/voltage cols → panel-aggregate correctly sources from 12 member feeders.
cards 8/8 conform, exec ok=8/8. RESPONSE rendered=6 partial=5 blank=2.
- c7 Context Rail: partial (real34/data45). honest gaps active_power_total_kw + voltage_ll_avg "not logged/measured by this meter" — TRUTHFUL (panel table has neither col + 0 rows). PASS.
- c5 Feeder Heatmap: partial real34/data102. real data present. PASS.
- c160 Heatmap Footer / c6 Live Scrubber: honest_blank (nav/legend cards, real0/data1 — no data leaves by design). PASS honest_gap.
- c8 AI Summary: text grounded — 300kVA rating REAL (asset_nameplate rated_kva=300 source=cmd_equipment_table, NOT fabricated class_default), power from live windowed data (BPDB peaks 683 last-15min, 500 within range). deterministic (no LLM call in ai log for it). PASS.
- c9 Total Supply: 1097.9kW real aggregate, _coverage reporting4/expected8 honest. PASS.
- c10 Consumption Trend: partial, honest gap active_power_total_kw not logged by panel meter — TRUTHFUL. PASS.
- c11 Quick Stats: real vals 236.0/5.82/1554.0, coverage 4/8 honest. PASS.
NO NaN, NO seed leak ("Sample" hits = field names sample_count/selectedSampleIndex), payload_error=None, errors={}.
VERDICT: 8/8 ok. honest_gaps=[6,160,and partial-leaf on 7,10]. NO DEFECTS.

---
## Batch3 Page 14 — 'transformer tap and rtcc for Transformer-01'  (run_id r_d06f6da969)
- routed: transformer-asset-dashboard/tap-rtcc == expected → ROUTED_OK
- asset: Transformer-01 = GIC-15-N3-PCC-01 (mfm_id 171, table gic_15_n3_pcc_01_transformer_01_se, class Transformer). asset_pending→re-POST 171 (name literally contains 'Transformer-01', has_data=true, class match; other cands 100174/306 also Transformer). 
- 1b contract_problem 'resolved asset but empty column_basket'; validate verdict=fail (n_columns 0) yet asset_gate proceeded → Layer 2. basket-resolution produced 0 cols for this table but cards still filled from neuract directly.
- neuract ground truth (24665 rows): tap_position/optimal_tap/tap_range/ts columns ABSENT (only timestamp_utc). 24h: voltage_avg 6373–6560 (real ~6.4kV), active_power_total_kw -1361 to -635 (real, substantial, negative). This is a MV transformer secondary — REAL nonzero data.
- cards 4/4 render, no payload_error.
- HONEST-BLANK CORRECT: card78 (tap_position/optimal_tap/tap_range col_absent → fully blank) + card80 (Recent Tap Changes, ts+tap_position col_absent → fully blank). Legit: this PQ MFM has no OLTC tap telemetry. (card80 'ts not measured' technically wrong wording — table has timestamp_utc not ts — but card is blank anyway, moot.)
- DEFECT (card 79→swap→44 Voltage History): REAL R/Y/B ~6.4kV series present, BUT contaminated with FABRICATIONS:
    * stats[0] 'Max Deviation' value = {min:216,max:264,nominal:240} — 240V-nominal band, PHYSICALLY WRONG for 6.4kV asset, NOT in stripped default (default was scalar 0.0) → injected fabricated 230V-nominal deviation band. Layer [ems_exec/fill or layer2-emit].
    * expectedMin=228 expectedMax=242 showExpectedRange=true — 240V expected band drawn over 6.4kV real data (default was 0.0) → fabricated band.
    * stats[2] 'Primary Event'='Motor start sag' — SURVIVING SEED LITERAL (verified: 'Motor start sag'+'Primary Event' present in cmd_catalog.card_payloads.payload_stripped for card 44); events col is column_absent yet canned event string leaks. Layer [card_payloads/strip].
    (minY/maxY/yTicks correctly from real data.)
- DEFECT (card 81 Tap Activity & Wear): activity.kpis[0] 'Total Tap count'=10153.4 unit '/5 million left' — FABRICATED tap-wear count from an active-power PROXY (note admits 'no dedicated tap counter, showing active power as proxy'). Meter measures ZERO tap ops → should be honest-blank, not a mislabeled power→tap-count proxy. Layer [layer2-emit] (proxy substitution) / [ems_exec/fill]. kpis[1]/[2] correctly blank.
- REASON-FIDELITY (cards 79,81): real substantial voltage/power (-1361 kW, 6.4kV) that blanked read denorm_garbage='Sensor reading below valid range' — same fault-narrative mislabel as page 13.

## BATCH1 v18_02 — 'energy and distribution for PCC Panel 1' — run_id r_075d05bffb
routed=panel-overview-shell/energy-distribution (EXPECTED verbatim) — routed_ok=TRUE. asset=PCC-Panel-1/317 AI Panel. 2/2 conform, exec ok=2/2. rendered=2 partial=2 blank=0.
- c12 Energy Input&Distribution (kpi+sankey): partial real11/data33. Peak kW value=null honest (panel meter). REAL energy 78140 kWh. PASS.
- c13 Energy Flow Diagram (sankey): partial real30/data88. feederOutputKw=913.8 REAL. Sankey VERIFIED against neuract:
    layer0 incomers(Solar1/2,Transf1/2)=None honest (0-row/absent tables); layer1 pcc-panel=78170; BPDB-01=78170
    (neuract import-delta-1d=78200 ✓ MATCH); UPS-01/02/03=0.0 which is REAL (neuract import-delta-1d=0.0 — UPS export
    meters, counter flat) NOT fabricated-zero; 4 feeders=None honest. loss/eff/sourceInput="—" honest. coverage 4/8.
NO NaN, NO payload_error, NO seed leak, 44 em-dash honest blanks. Mass-balance correct.
VERDICT: 2/2 ok. honest_gaps on non-reporting incomers/feeders (truthful). NO DEFECTS.

### Page 08 | 'energy and power for GIC-01-N3-UPS-01' | run_id r_bb525a5212
- routed: individual-feeder-meter-shell/energy-power — MATCHES expected. routed_ok=TRUE. 1b pinned same UPS mfm_id=11 (verified). 4 cards 39/40/41/42, all with_payload, no payload_error.
- CARD 39 (Today's Energy) — DEFECT [layer2-emit]: data.reactiveEnergyKwh=21993.0 is the RAW LIFETIME cumulative counter (reactive_energy_import_kvarh, agg=last per data_instructions) shown in a "Today's Energy" card; today's real delta is 8 (DB: today min21985→max21993). Real column value but wrong aggregation (should be windowed_delta like totalEnergyKwh=231). Inflated ~2750x, mislabeled under kWh. activeEnergyKwh=0.0 is the truly-dead active counter (1 distinct value, honest). ratedKw n/a here.
- CARD 40 (Power Energy Analysis, energy-power-history) — DEFECT [ems_exec/fill]: data.bars[*] all {active:0,reactive:0,time:""} AND demandBars[*].value all 0.0 — yet both bind bucketed active_power_total_kw which HAS real data (verified today n=136 avg -203.7 kW) and the SAME-column hourlyAverage[] filled real (~185-203). So the primary bar chart + demand bars render EMPTY despite live data = fill gap, not honest-blank. demandBars[*].band = seed strings low/moderate/high (in payload_stripped) → [card_payloads/strip]. activePowerAvgKw/reactivePowerAvgKw/yMax/yMin='—' honest-blank. ratedKw=540 (=600kVA×0.9, nameplate real via asset_nameplate source=cmd_equipment_table), contractedKw=486 derived-from-rated (contracted_kva empty) — acceptable, rated grounded.
- CARD 41 (Input vs Output Energy) — OK: hvInputKw=lvOutputKw=205.7 (real active power). lossKwh/deltaPct/efficiencyPct/lossPctOfInput='—' honest-blank (no HV-side meter to compute loss). expectedLossKwh=0.0 (target_efficiency unset → but shows 0 not '—'; minor). No fabrication.
- CARD 42 (Load Anomalies, load-anomalies) — DEFECT [card_payloads/strip]: 5 anomaly objects with FABRICATED seed label/title strings ('Welding Overlap','Motor start','Compressor cycling','Early Shut down','Compressor trip') survive from card_payloads.payload_stripped (VERIFIED both story rows still carry these strings). All numeric leaves honestly zeroed (value/deviationPct/durationMs=0, time='', surgeEvents/dipEvents/loadFactorPct/presentValuePct=None, yMax/yMin=None), actualLoad/expectedLoad all 0. So the card renders 5 fictional anomaly events that never occurred → violates contract(d) no surviving seed. The host banner claim "seedless payload_stripped" is FALSE for non-numeric string leaves.
- VERDICT: cards_ok=1/4 (only 41). defects: card39 emit-agg, card40 fill-empty-bars + seed-bands, card42 seed anomaly labels. honest_gaps: card41 loss leaves. infra_down=false.

---
## Batch3 Page 15 — 'transformer thermal life for Transformer-01'  (run_id r_f3b19721cb)
- routed: transformer-asset-dashboard/thermal-life == expected → ROUTED_OK
- asset: Transformer-01 mfm_id 171 (same as p14), re-POST 171.
- neuract ground truth (gic_15_n3_pcc_01_transformer_01_se): ALL thermal cols ABSENT (winding_temp, oil_temp, hotspot_temperature_c, aging_factor, life_used_pct, loss_of_life_pct, loss_kw, stress_pct). active_energy_import_kwh + reactive_energy_import_kvarh columns EXIST but 0 non-null rows/48h (DEAD counters). apparent_power_total_kva REAL (4467 rows, 638–1365 kVA). active_power_total_kw real.
- cards 4/4 render, no payload_error.
- HONEST-BLANK CORRECT (majority): thermal-life needs winding/oil/hotspot/aging telemetry this PQ MFM lacks → column_absent gaps CORRECT (cards 74,76,77 blank thermal leaves). structurally_null on dead energy counters CORRECT (card75 lifeFillPct, card77 deltaLolPct). card77 fully honest_blank — LEGIT (no aging inputs exist).
- DEFECT (card 75 Life & Capacity): lifeCapacity.lifeRemainingYears = 10151.7 (unit 'years', lifeBaseYears=40) — PHYSICALLY ABSURD (10151 yrs remaining on a 40-yr transformer). ROOT CAUSE: data_instructions binds slot lifeRemainingYears → fn 'todaysEnergyTotalKwh' over active_energy_import_kwh/reactive_energy_import_kvarh (DEAD counters) → ems_exec ∫power fallback integrated the live power series → ~10151.7 kWh → stuffed into a 'years' leaf. layer2-emit MIS-BOUND a life-remaining metric to an energy-integral fn; ems_exec/fill ∫power fallback filled a semantically-wrong leaf. Default was 0.0 (scrubbed) → fabrication injected at fill. Should be honest-blank (aging inputs absent). Layer [layer2-emit] + [ems_exec/fill]. (Note: 10151.7 mirrors p14's 10153.4 fake tap-count — same power-integral leak.)
- CONCERN (card 74 Thermal Life): winding/oil/loss VALUES all column_absent (blank) yet metrics[*].tone='normal', statusLabel='Normal', status.label='Stable' NOT blanked → implies thermally-healthy transformer with ZERO thermal data. Misleading status-fabrication (status leaves should degrade with their values). card75 status.label='Stable' same. Layer [ems_exec/fill] (status/tone leaves not gated on the measured value).
- REASON-FIDELITY (card 75 deratedKva/deratedFillPct): real apparent/active power blanked denorm_garbage='below valid range' — same mislabel as p13/p14.

## BATCH1 v18_03 — 'energy and power for PCC Panel 1' — run_id r_99879f110d
routed=panel-overview-shell/energy-power (EXPECTED verbatim) — routed_ok=TRUE. asset=PCC-Panel-1/317 AI Panel. 4/4 conform, exec ok=4/4.
- c14 Cumulative Energy: REAL 78240 kWh active + 1030 kVArh. capacityValue/target/sec/markerPct = "—" honest (no panel nameplate). PASS.
- c15 Today live power: REAL 829 kVA / 823 kW / 36.9 kVAr. load-factor/capacityValue/markerPct/markerLabel = "—" with EXPLICIT honest-null const bindings ("why: worst-peak marker % needs rated capacity ... honest-null never a fabricated 0"). EXEMPLARY. PASS.
- c16 Energy Trend: REAL points ups=0.0(real import-delta=0)/bpdp=74990/total. HHF="—" honest (no HHF member). PASS.
- c17 Daily Power Demand by Feeder: **DEFECT**. 25-pt series REAL (ups~600 [neuract UPS-sum=607.7 MATCH], bpdp~330). BUT demand.view.stats[worst-peak]=0.0 and stats[load-factor]=0.0 are FABRICATED DERIVED-ZERO seed leaks: series clearly peaks ~610 UPS/~955 combined, yet Worst Peak shows 0 kW / Load Factor 0%. Also criticalKw=0.0, sub="at 17" seed text. ROOT CAUSE: card_payloads.payload_stripped(card 17) retains demand.view.stats value:0.0 (numeric seed NOT stripped to null) + data_instructions.roster has NO binding for demand.view.stats (unlike c15 which emits honest-null const w/ "why"). Contrast c15 (correct honest-null) vs c17 (leaked seed). layer=build/strip + layer2-emit. SYSTEMIC: same surviving stats value:0.0 in stripped payload for cards 11,17,44,46,49,67,69 (leaks only when roster doesn't bind the slot).
VERDICT: 3/4 ok (14,15,16). card 17 DEFECT (fabricated derived-zero stats). NO NaN elsewhere, no payload_error.

### Page 09 | 'power quality for GIC-01-N3-UPS-01' | run_id r_1bc17049b9
- routed: individual-feeder-meter-shell/power-quality — MATCHES. routed_ok=TRUE. 1b same UPS. 3 cards 47/48/49, verdict pass_with_gaps. Payloads under keys snapshot/distortionProfile/loadImpact (data=null is by-design, not a defect).
- DB ground-truth (UPS today): thd_current_r/y/b_pct REAL(5-9%), thd_compliance_i_avg REAL(5.4-7.9), harmonic_5th/7th present; but thd_voltage_r/y/b_pct=0-non-null, thd_compliance_v_avg=0-non-null, thd_compliance_ieee519=0-non-null (V-THD/IEEE519 NEVER measured). PF: kpi_true_pf REAL(0.99-1.0), power_factor_total/kpi_displacement_pf REAL(0.999), pf_gap_vs_full_load REAL(-2.0).
- CARD 47 (Power Quality) — DEFECT [card_payloads/strip]: iThd/h5/h7 REAL (5.5/6.5/5.5). BUT vThd.valuePct=0.0, flickerPst.value=0.0, crestFactor.value=0.0 shown for UNMEASURED leaves (should be '—') = derived-zero fabrication; and ieeeBadge="IEEE 519 Fail"/ieeeState="fail" + filterState="APF active" are FABRICATED verdict/state strings surviving in payload_stripped (VERIFIED main story still carries vThd=0.0, ieeeBadge fail, flicker/crest 0.0, APF active) while thd_compliance_ieee519 is 0-non-null in DB. Renders a fabricated IEEE-519 FAIL judgment on never-measured compliance.
- CARD 48 (Distortion & Harmonic Profile) — DEFECT [card_payloads/strip + design]: i-thd view REAL (yMax 8.97, 3 phase THD series real). BUT default view = 'v-thd' (seed default) whose series are zero/empty (V-THD unmeasured) → card opens on an EMPTY chart hiding the real i-thd data; maxLine 'Max: 480V'/'Max: 480A' + minLine '410 V/A' are seed labels (value 0.0). h5-h7 view empty (yMax=0).
- CARD 49 (Load Impact & Transformer Stress) — DEFECT [ems_exec/fill + card_payloads/strip]: pf-health view True PF=None AND Power Factor=None despite REAL kpi_true_pf(0.99-1.0) & power_factor_total(0.999) in DB (fill gap); PF Gap(displ.)=0.999 is WRONG (real pf_gap_vs_full_load=-2.0) → mis-bound/fabricated; PF Target=0.0 seed. k-stress/pf-angle stats = FABRICATED verdict strings 'Heating Risk','Reduce I-THD','Stable/Raising','Watch' (VERIFIED in payload_stripped) with all series empty (nonempty=0).
- VERDICT: cards_ok=0/3. defects: 47 seed vThd/ieee/flicker/crest+fabricated IEEE-fail; 48 empty default v-thd view+seed labels; 49 None-PF despite real data + wrong PF-gap 0.999 + seed verdicts. honest_gaps: 47 partial-note (V-THD/flicker/crest genuinely unmeasured — the note is honest, but the leaves were shown 0.0 instead of '—'). infra_down=false.

---
## Batch3 Page 16 — 'ups battery and autonomy for GIC-01-N3-UPS-01'  (run_id r_8cfd3d6cf1)
- routed: ups-asset-dashboard/battery-autonomy == expected → ROUTED_OK
- asset: PINNED confidently GIC-01-N3-UPS-01 CL:600KVA (mfm_id 11, table gic_01_n3_ups_01_p1, class UPS). No ambiguity — no re-POST.
- neuract ground truth (53363 rows, 72 cols): ZERO battery-mgmt cols (no soc/batt/charge/autonomy/backup/temp/score — it's a plain V/I/power PQ MFM). active_power_total_kw REAL -227 to -157 kW (3357 rows/24h). active_energy_import_kwh present but FLAT 0 (6741 rows all 0).
- cards 4/4 render, no payload_error.
- HONEST-BLANK CORRECT (majority): SOC/battery-temp/output-V/I (card50 fully blank), battery scores/DC-bus/thermal (card51), autonomy/backup-time/load scores (card53) all column_absent — this UPS meter has no battery telemetry. LEGIT.
- DEFECT (card 52 Backup Readiness): backupReadiness.metrics[0] 'Backup time' = 231.0 min, tone=success/'Normal'. Binding fn=todaysEnergyTotalKwh over active_energy_import_kwh (FLAT 0) → ∫power fallback integrated real power (-227kW series) → ~231 kWh → MISLABELED as '231 minutes backup time'. Same energy-integral-into-wrong-leaf class as p15's 10151.7yrs. Fabricated (no battery autonomy telemetry). Layer [layer2-emit] mis-bind + [ems_exec/fill] ∫power fallback.
- DEFECT (card 52): metrics[2] 'Transfer Mode' = 'Inverter' — SURVIVING SEED LITERAL (verified 'Inverter' in cmd_catalog.card_payloads.payload_stripped card 52). No source/transfer column exists → fabricated source-state. tone=success/'Normal' compounds. Layer [card_payloads/strip].
- CONCERN (card 52 metrics[0]): fake 'Normal'/success status on the fabricated 231 value. metrics[0].value=231 real-looking; metrics[1] Headroom correctly '—'. (Also metrics[0] earlier-listed 231.0 IS the backup-time fabrication.)
- CONCERN (card 53): render 'partial' real=14/19 MISLEADING — the 14 'real' leaves are static chart chrome (yTicks, zone bounds/colors, thresholds), EVERY actual data series (autonomy index, backup-time score, load scores) is column_absent/blank. No fabricated data points (defensible) but answerability overstated.
- REASON-FIDELITY (card 52 backupReadiness.score): real active_power blanked denorm_garbage='below valid range' — same mislabel.

---
## Batch3 Page 17 — 'ups output load capacity for GIC-01-N3-UPS-01'  (run_id r_e02e4237bf)  *** SEVERE ***
- routed: ups-asset-dashboard/output-load-capacity == expected → ROUTED_OK
- asset: PINNED GIC-01-N3-UPS-01 mfm_id 11 (table gic_01_n3_ups_01_p1). 1b basket_cols 47, validate verdict=PASS (this page maps to the meter's REAL columns).
- neuract ground truth (24h, 3356 rows each): voltage_avg 226.9–239.7 V (latest 236.7), current_avg 222–326 A (latest 278), frequency_hz 49.8–50.2 (latest 50), active_power_total_kw -227 to -157 (latest -196.5). ALL real, valid, in-range, LIVE (230V/50Hz/278A UPS input).
- SEVERE DEFECT [ems_exec/fill] history/bucketed fill DROPS real data + MISLABELS as sensor-fault:
    * card 59 Composite: composite.points = 0 (EMPTY) → every per-point leaf (inputVoltageV=voltage_avg, inputCurrentA=current_avg, bypassFrequencyHz=frequency_hz, loadPct=active_power) blanked as denorm_garbage='Sensor reading below valid range'. FALSE — data exists & is in-range.
    * card 58 UPS Load: load.sparkline = 30× loadPct 0.0 = the UN-OVERWRITTEN Storybook DEFAULT (default is 30 entries all 0.0, labels -29d..0d) → fabricated '0% load 30d' series shown while real load ~197kW. Bucketed fill left the seed zeros, didn't blank. + averageLoadPct blanked denorm_garbage.
    * card 57 UPS Capacity: all scoreCells '—', loadFactorPct derivations blanked as denorm_garbage (likely no rated_kva nameplate wired → should be no_nameplate reason, mislabeled).
  PROOF the data is reachable via the SAME pipeline path: ems_exec.data.neuract.bucketed('gic_01_n3_ups_01_p1','active_power_total_kw',<card window>,'hourly') → returns 25 REAL hourly pts (-200.7,-197.0,-185.3 kW…); latest() → 236.9V/305A/-217kW. So the request-time fill drops these while a direct call works. Root cause = fill's history/bucketed series path (not the fetcher, not the DB).
- Only real leaf that surfaced: card58 scoreCells[0]=197.9 (raw latest active_power kW) — confirms latest-row raw path works, history/derived paths broken.
- REASON-FIDELITY: every blank reads denorm_garbage='below valid range' — DOUBLY wrong here (data exists AND is in range; fetch/fill dropped it). This mislabel HIDES the real bug behind a fake sensor-fault narrative.
- This page's cards render structurally (no payload_error) but violate contract (c) real-where-measured: real V/I/Hz/power exist and are fetchable but not shown; and (d) zero-fabrication: card58 shows default-zero sparkline.

### Page 10 | 'dg voltage and current for DG-1' | run_id r_c7938ef357 (asset_pending → re-pinned asset_id=2)
- routed: diesel-generator-asset-dashboard/voltage-current — MATCHES. routed_ok=TRUE.
- ASSET-PICKER: 1st pass ambiguous, offered 2 DG-CLASS candidates (mfm_id=2 DG-1 MFM has_data=T; mfm_id=300 GIC-28-N1-DG-01 has_data=F). Class-match correct. Re-pinned asset_id=2 (DG-1 MFM, literal "DG-1" match + has data) → how=user-choice, 4 cards 66→swap43 / 67→swap44 / 68 / 69.
- GROUND TRUTH: dg_1_mfm has 45606 rows but voltage_ry/current_avg/active_power ALL 0 (d_vry=1 distinct, all-time max=0, zero non-zero rows) → the DG is genuinely OFF/idle (dead-zero meter). So numeric 0.0 on live cards = REAL telemetry of an off generator (defensible), deltas/unbalance='—' honest.
- CARD 66 (Voltage Live Health, swap→43) — DEFECT [card_payloads/strip]: status={tone:warning,label:"Elevated"} — a FABRICATED alarm verdict on 0 V (DG off); phases value=0.0 real-off, delta/deltaTone='—' honest, markerPct null honest.
- CARD 67 (Voltage History, swap→44) — DEFECT [card_payloads/strip]: 12 FABRICATED voltage sag/swell events (fixed indices 7,15,24,27...) + stats "Primary Event":"Motor start sag" surviving from payload_stripped (VERIFIED card 44 main story carries 'Motor start sag' + 12 events), rendered on an ALL-ZERO series (DG off, no events possible). stats Max Deviation/Worst Spread='—' honest. series all 0.0 honest-off.
- CARD 68 (Current Live Health, keep) — BORDERLINE OK: phases R/Y/B/N=0.0 real-off, Avg/Neutral=0.0 real-off, Unbalance='—' honest. status "Normal" is a mild seed verdict on off-data (not alarming); not faulted.
- CARD 69 (Current History, keep) — DEFECT [fabricated capacity]: series all 0.0 honest-off, stats all 0.0 honest; BUT maxLine "Rated: 131A" value=131.0 injected via data_instructions const metric=I_RATED while asset_nameplate.dg_1_mfm has rated_kva='' source='none' (NO real nameplate) → 131A is an ungrounded/class-default fabricated rating (matches known DG fabricated-rating bug); label string "Rated: 131A" also seed.
- VERDICT: cards_ok=1/4 (68). defects: 66 fabricated "Elevated" status; 67 fabricated 12 events + "Motor start sag"; 69 fabricated "Rated: 131A" (no nameplate). honest_gaps: deltas/unbalance/deviation '—' across cards (DG off). infra_down=false.
- NOTE: page renders honestly for an OFF DG on the numeric leaves, but seed verdicts/events/rating fabrications leak through the strip.

## BATCH1 v18_04 — 'harmonics and power quality for PCC Panel 1' — run_id r_a68ae6e694
routed=panel-overview-shell/harmonics-pq (EXPECTED verbatim) — routed_ok=TRUE. asset=PCC-Panel-1/317 AI Panel. 5 cards, swaps c24->20 c25->19. exec ok=5/5. Members have rich THD/harmonic cols (verified UPS-01 THD_r=7.3%, h5/h7, current_neutral, unbalance).
- c23 PQ Issues KPI Strip: **DEFECT (fabricated seed)**. strip.stats.worstIThd is REAL+correct (id=gic-01-n3-ups-01, iThd=6.23, kw=206.1, neutralA=19.1 — matches neuract). BUT the legacy strip.stats.WORST object is a surviving Storybook seed: {id:"ups-05", table:"MFM_034", status:"danger", driver:"5th harmonic current distortion", h3/h5/h7/iThd/kw/pf/kFactor all 0.0}. MFM_034 does NOT exist in neuract (count=0). Confirmed identical block in card_payloads.payload_stripped(23). Tiles themselves show None (honest "—") but the .worst seed rides in payload w/ FAKE danger status. layer=build/strip + layer2-emit(aggregates writes worstIThd but leaves legacy .worst seed).
- c24 Harmonics&PQ Timeline (->20): REAL amps=291,vAvg=236.7(phase),vMax=239,neutralA=19.1,iUnbalance=3.78,h-data. sag=0/swell=0 REAL (neuract BPDB 1d sags=0 swells=0). neutral=0 timeline count (neutral_stress active-samples=1510 but discrete-event count defensibly 0) — borderline, PASS. No fake tables.
- c25 AI Summary (->19): **DEFECT (fabricated seed roster)**. widgets.ai_summary.text is REAL+grounded ("4 of 8 members... GIC-01-N3-UPS-01 highest current THD 7.0%"). BUT summary.stats carries TEN fabricated MFM_0xx table refs (MFM_023..MFM_061) + worstCurrent{id:ups-04,table:MFM_033,status:"warning"} + worstVoltage{ups-05} — ALL fake (MFM_033 count=0 in neuract), identical to seed payload_stripped(19). ALSO render verdict=honest_blank/answerability=none INCONSISTENT with a real ai_summary text present. layer=build/strip (whole seed feeder-roster survived) + layer2-emit.
- c26 Feeder PQ table (->26): REAL kw=206.1. pres.* zeros = layout config (rowHeight/fit/decimals) not data. No fake tables. PASS.
- c27 Signature (->27): REAL h5=7.0,h7=4.8,kw=206.1. pres.* zeros = style config. No fake tables. PASS.
VERDICT: 3/5 ok (24,26,27). c23 + c25 DEFECT (surviving fabricated MFM_0xx seed rosters + fake danger/warning statuses). SYSTEMIC strip gap: nested seed objects w/ fake tables+hardcoded status not nulled; aggregate binds NEW key leaving legacy seed key.

---
## Batch3 Page 18 — 'ups source transfer for GIC-01-N3-UPS-01'  (run_id r_d7be9457fc)
- routed: ups-asset-dashboard/source-transfer == expected → ROUTED_OK
- asset: PINNED GIC-01-N3-UPS-01 mfm_id 11. 1b basket_cols 53, validate PASS.
- cards 3/3 render, no payload_error. (Same asset/table as p16/17 — V/I/Hz/kW all real, verified p17.)
- HONEST-BLANK CORRECT: card 55 Activity FULLY honest via derivation_unbound (Last Transfer/Lifetime/30-day/Activity-Ticks — 'not computed, no derivation binding configured'). LEGIT: this input meter has ZERO transfer-event telemetry. Cleanest card of the batch — accurate reason.
- REAL AGGREGATES DID surface (card 56): 'Bypass (Hz)'=50.0 (real freq), 'Average Bypass Voltage'=237.07 (real, matches neuract 236-239V) → latest-row/aggregate fill path WORKS.
- DEFECT [ems_exec/fill] (card 56 Composite): composite.points = 0 (EMPTY) — same broken history/bucketed series fill as p17. Per-point inputVoltageV/inputCurrentA/bypassFrequencyHz blanked denorm_garbage='below valid range' while the data is real+fetchable (bucketed() returns 25 pts, proven p17). Aggregate legend values real; time-series dropped.
- CONCERN (card 54 Transfer readiness): readiness.score + all sub-scores blanked (denorm_garbage on real active_power); only chart chrome present. Proxy note 'load factor as proxy for transfer readiness'. Bypass score honestly '—'.
- REASON-FIDELITY: denorm_garbage='below valid range' on real V/I/Hz again (p16/17/18 pattern).
- No surviving seed VALUES (Bypass strings are labels only).

### Page 11 | 'dg engine and cooling for DG-1' | run_id r_dd90453138 (asset_pending → re-pinned asset_id=2)
- routed: diesel-generator-asset-dashboard/engine-cooling — MATCHES. routed_ok=TRUE. Same 2 DG-class candidates; re-pinned asset_id=2 DG-1 MFM (only DG with data). 3 cards 60/61/62.
- CONTEXT: DG-1 MFM is an ELECTRICAL-only PLC meter (34 basket_cols) with NO thermal/oil-pressure/RPM columns, and its electrical columns are all 0 (DG off). Render layer honest-blanks aggressively with per-LEAF reasons — GOOD.
- CARD 60 (Engine 3D Callout Viewer) — HONEST-BLANK/OK: render.verdict=honest_blank reason "these metrics not logged by this meter"; object=null template=null (no asset_3d model for a PLC meter). Counts as the 1 'blank' card. Honest gap, PASS (no fabrication).
- CARD 61 (Thermal Timeline) — DEFECT [card_payloads/strip]: KPIs Peak Exhaust/Max Coolant='—' honest, all 4 series blanked (denorm_garbage: active_power/freq/pf/current all 0), Events KPI=0 honest, render.verdict=partial with full gap list — EXCELLENT honest degrade. BUT events[] carries 2 FABRICATED seed alarms 'Exhaust over-temp'(danger,80C,-15h) + 'Coolant high'(warn,100C,-10h) (VERIFIED in payload_stripped) on a meter with NO thermal columns → false alarm annotations.
- CARD 62 (Pressure·Speed·Load) — DEFECT [card_payloads/strip]: KPIs Peak/Avg Load + Min Oil-P='—' honest, series blanked, render.verdict=partial honest. BUT events[] carries FABRICATED seed 'Oil pressure low'(warn,-2h) (VERIFIED in payload_stripped); no oil-pressure column exists.
- NOTE (not a defect): L2 emit-note claimed it'd show electrical proxies (power→load, freq→speed) as stand-ins; render layer correctly caught the proxy data as all-zero denorm_garbage and BLANKED it → no misleading power-as-temperature values actually rendered. Honest.
- VERDICT: cards_ok=1/3 (60 honest-blank). defects: 61 seed thermal events, 62 seed oil-pressure event. honest_gaps: 60 (no 3D model), 61/62 all thermal/mech KPIs+series (meter lacks columns). infra_down=false.

### Page 12 | 'dg fuel efficiency for DG-1' | run_id r_1f97dfa47f (asset_pending → re-pinned asset_id=2)
- routed: diesel-generator-asset-dashboard/fuel-efficiency — MATCHES. routed_ok=TRUE. Same 2 DG candidates; re-pinned asset_id=2 DG-1 MFM. 3 cards 63/64/65.
- NOTE: 1b logged contract_problems=['resolved asset but empty column_basket'] + validate verdict=fail, yet asset_gate proceeded → Layer 2 (per-leaf degradation policy: verdicts=telemetry not gates — consistent with V48 rule). DG-1 MFM electrical meter has NO fuel/tank/SFC columns.
- CARD 63 (Fuel Tank Anatomy) — HONEST-BLANK/OK: render.verdict=honest_blank, ALL leaves null (autonomy/fuelRate/fuelTemp/fuelLevel/efficiency + display.* all null) with per-leaf 'not measured by this meter' reasons. The 1 'blank' card. PASS, zero fabrication.
- CARD 64 (All Runs / Fuel Log) — BORDERLINE OK: faults/starts/avgLoad/runHours=null honest, totalKwh=0.0 real-off. Minor: totalFuelL=0.0 (no fuel column → should be null, 0.0 is a benign derived-zero, no false alarm). render.verdict=partial honest. Not faulted.
- CARD 65 (Fuel & Tank Composite) — DEFECT [card_payloads/strip]: KPIs Efficiency/SFC/Load='—' honest, all series zero (honest), render reason honestly cites 'Rated capacity unknown for dg_1_mfm — loading %% unavailable' (matches empty nameplate). Cost=0.0 minor derived-zero. BUT events[] carries 2 FABRICATED seed 'Reserve low' fuel alarms (-16h,-8h) (VERIFIED in payload_stripped) on a meter with NO fuel-level column → false alarms.
- VERDICT: cards_ok=2/3 (63 honest-blank, 64 borderline-ok). defects: 65 fabricated 'Reserve low' events. honest_gaps: 63 all-null (no fuel data), 65 Efficiency/SFC/Load + loading% (meter lacks columns). infra_down=false.

## Batch 2 SUMMARY (pages 07-12)
- ALL 6 pages routed CORRECTLY to the class-appropriate page (routed_ok=TRUE on all). Asset-picker correctly offered only DG-class candidates for DG prompts (10/11/12) and pinned the UPS confidently (07/08/09). No class-mismatch defects.
- DOMINANT DEFECT PATTERN [card_payloads/strip]: payload_stripped retains fabricated NON-NUMERIC leaves — verdict/status strings ('IEEE 519 Fail','Elevated','Heating Risk','Reduce I-THD'), advisory events ('Welding Overlap','Motor start sag','Exhaust over-temp','Coolant high','Oil pressure low','Reserve low'), and axis/line labels ('Max: 480V','Rated: 131A') — even though numeric leaves are correctly zeroed/blanked. Host banner claim "seedless payload_stripped, ZERO runtime strip" is FALSE for string leaves. Affected cards: 40,42,47,48,49,66,67,69,61,62,65.
- SECONDARY [ems_exec/fill]: card 40 bars/demandBars all-zero despite real active_power (hourlyAverage same-column filled); card 49 True PF/Power Factor=None despite real kpi_true_pf/power_factor_total, PF Gap 0.999 wrong (real -2.0).
- [layer2-emit]: card 39 reactiveEnergyKwh=21993 (raw cumulative counter via agg=last on a 'today' card; real delta=8).
- [fabricated capacity]: card 69 'Rated: 131A' (I_RATED const) with NO nameplate (asset_nameplate rated_kva='' source='none').
- The render layer (pages 11/12) honest-blanks NUMERIC leaves excellently with per-leaf reasons — the gap is purely the seed STRING/event leaves leaking through strip.
- infra: neuract :5433 UP throughout; all cross-checks succeeded. No infra_down.

## BATCH1 v18_05 — 'voltage and current for PCC Panel 1' — run_id r_b57a82feb3
routed=panel-overview-shell/voltage-current (EXPECTED verbatim) — routed_ok=TRUE. asset=PCC-Panel-1/317 AI Panel. 5 cards no swap, exec ok=5/5.
- c18 Events KPI Strip: REAL — worstCurrent{iThd=6.3, mfmId=11 (UPS-01 REAL id), truePf=0.995, neutralA=14.7, iUnbalance=3.18, vDeviation=-1.04}. Uses REAL mfmId not fake table. sag/swell/total=0 event counts. PASS.
- c19 AI Summary (render 19): **DEFECT** — same as v18_04: summary.stats carries 10 fake MFM_0xx tables (023..061) + worstCurrent{table:MFM_033,status:warning} all fabricated seed; verdict=honest_blank inconsistent w/ (likely real) ai_summary text. layer=build/strip+layer2-emit.
- c20 Event Timeline: REAL amps=283,vAvg=237.5,vMax=239.4,neutralA=14.7,iUnbalance=3.18. No fake tables. PASS.
- c21 Current Distribution: **DEFECT (mixed)**. amps/current REAL per feeder (UPS-01=283/02=287/03=295/BPDB-01=188 match neuract current_avg; 4 dark feeders None honest). BUT: every panel.table = FAKE MFM_0xx (real is gic_*), mfmId=None; AND vAvg=0.0/neutralA=0.0/iUnbalance=0.0 for ALL panels are FABRICATED-ZEROS (UPS-01 voltage_ll_avg=412.1 REAL exists → 0.0 is fabricated not honest). 8 fake tables. layer=layer2-emit (roster bound amps+names but left seed table+fabricated-0 ancillary fields) + build/strip.
- c22 Other Panels table: REAL amps=283,vAvg=237.5,neutralA=14.7,iUnbalance=3.2. No fake tables. PASS.
VERDICT: 3/5 ok (18,20,22). c19 + c21 DEFECT (fake MFM_0xx seed tables; c21 fabricated-zero voltages). Same systemic strip/emit gap.

## BATCH1 v18_06 — 'voltage and current for GIC-01-N3-UPS-01' — run_id r_aea5abb769
routed=individual-feeder-meter-shell/voltage-current (EXPECTED verbatim) — routed_ok=TRUE. CLASS-CORRECT: asset=GIC-01-N3-UPS-01 mfm_id=11 class_prior=UPS (NOT Panel — right class). Single-asset reads OWN table gic_01_n3_ups_01_p1 (53342 rows). 4 cards no swap, exec ok=4/4. NO fake MFM tables anywhere (single-asset path clean).
- c43 Voltage Live Health: REAL phases R=237.3 Y=236.5 B=239.6 V, Unbalanced=0.757%, band 216/240/264. gap metrics[2] "ts not measured" honest; Rate Change="—" honest. tailPct/widthPct=0.0 = gauge-fill chrome (delta="—" honest). PASS.
- c44 Voltage History: **DEFECT**. R/Y/B series REAL (25/25 nonzero pts ~237/236/240V), maxY=240.9 minY=227.6 REAL. BUT: stats[2] "Primary Event"="Motor start sag" = FABRICATED SEED STRING (no event detection); Worst Spread=0.0 (real spread ~13.3V); maxLine.value=0.0 + minLine.value=0.0 (should be 240.9/227.6 — would render broken ref-lines at 0 on 227-241V chart); expectedMax/Min=0.0. All confirmed identical in card_payloads.payload_stripped(44). CONTRAST sibling c46 which fills maxLine=296/minLine=279 CORRECTLY → c44 binding gap. layer=layer2-emit (voltage-history roster didn't bind maxLine/minLine/spread/event) + build/strip (seed 'Motor start sag'+0.0 survived).
- c45 Current Live Health: REAL phases 287/279/296 A + neutral 14.73, Unbalance=3.136%. PASS.
- c46 Current History: CLEAN — series REAL, maxLine=296/minLine=279 REAL, stats Peak296/Avg287/Unbal3.14/Neutral14.73 REAL, expectedMax=600 (rating) expectedMin=0 legit. PASS (the correct reference for c44).
VERDICT: 3/4 ok (43,45,46). c44 DEFECT (fabricated 'Motor start sag' event string + fabricated-zero maxLine/minLine/spread while sibling c46 binds them correctly). Best page of batch (single-asset, no fake rosters).

## BATCH1 SUMMARY (pages 01-06)
Routing: 6/6 CORRECT (all verbatim page_key match; page 06 correctly class-matched UPS mfm_id=11 not a Panel).
Infra: UP throughout (5433 open, host live). NO infra_down.
Cards: 32 total, 22 ok, 10 DEFECT.
DEFECTS — one SYSTEMIC root cause dominates: card_payloads.payload_stripped retained Storybook seed values (numeric 0.0 in nested stats/reference objects, fake feeder-roster tables 'MFM_0xx', hardcoded alarm statuses 'danger'/'warning', event narrative strings 'Motor start sag') AND the layer2-emit roster binds a NEW/parallel key (e.g. worstIThd) or the real series but does NOT overwrite/null the legacy seed leaf. Result = fabricated data rides alongside real data (contract (d) violation).
  - c17 (p03): stats worst-peak/load-factor = 0.0 seed (series peaks ~610kW).
  - c23 (p04): strip.stats.worst = seed {MFM_034, status danger, 0.0} beside REAL worstIThd=6.23.
  - c25 (p04) / c19 (p05): AI-Summary summary.stats = 10 fake MFM_0xx feeder roster + worstCurrent{MFM_033,warning}; honest_blank verdict yet real ai_summary text present.
  - c21 (p05): real per-feeder amps BUT panel.table=fake MFM_0xx + vAvg/neutralA/iUnbalance=0.0 fabricated (real voltage 412V exists).
  - c44 (p06): 'Motor start sag' seed string + maxLine/minLine/spread/expected = 0.0 seed (sibling c46 fills them correctly → binding gap).
Clean single-asset feeder path (p06) carries NO fake rosters — the fabrication is concentrated in PANEL-AGGREGATE PQ/summary/distribution cards whose seed defaults ship a full mock feeder roster.
POSITIVES: real data verified against neuract everywhere it's claimed (supply aggregates, THD 6.3%, phase V 237, currents 283-296A, energy 78MWh, UPS import-delta=0 honest-zero); honest-blank '—' with per-leaf reasons is pervasive and truthful; c15 is the EXEMPLAR of correct honest-null const-binding with "why". NO NaN, NO payload_error, NO whole-card refusal anywhere.

---

## CROSS-CLASS / EDGE prompt batch — verification (log-grounded)
Run 2026-07-05. Host :8770 (fixed pipeline), read-only. Each prompt → run_id via host.log; classify OK / DEFECT(family) / honest-degrade.

### cross_1  "Real-time power of DG-03 Jackson"  run_id=r_ea44a73ed2
- 1a: page=diesel-generator-asset-dashboard/operations-runtime (DG class, correct), metric=power, cards=4
- 1b: asset=None candidates=2 how=ambiguous class_prior=DG
- asset_gate: pinned=False verdict=asset_pending → asset popup (Layer 2 NOT run)
- Candidates surfaced: (a) DG-3 MFM mfm_id=4 has_data=true, (b) GIC-28-N3-DG-03 [Jackson] mfm_id=302 has_data=false
- VERDICT: **OK (honest picker)** — HOMONYM correctly disambiguated; named "Jackson" asset (302) IS offered; did NOT silently render the live DG-3 MFM data as the answer. Correct anti-mis-pin.

### cross_2  "Load profile of UPS-04 over the last 24 hours"  run_id=r_a280d5c50b
- 1a: page=ups-asset-dashboard/output-load-capacity (UPS class, correct), metric=power, intent=trend
- 1b: how=ambiguous, 3 candidates: 191 GIC-17 UPS-04 [TiMAC] has_data, 299 GIC-27 UPS-04 [TiMAC] has_data, 23 GIC-02 UPS-04 (no data)
- asset_gate → asset_pending → picker. VERDICT: **OK (honest picker)** — 3 real UPS-04 homonyms, all offered, none silently rendered.

### cross_3  "UPS-01 load percentage right now"  run_id=r_c1bb1de592
- 1a: page=ups-asset-dashboard/output-load-capacity, metric=power, intent=snapshot
- 1b: how=ambiguous, 5 candidates all named UPS-01 (11,188,192,194,296) all has_data=True
- VERDICT: **OK (honest picker)** — heavy homonym (5 UPS-01 across GIC-01/17/27), all recalled, no silent pin.

### cross_4  "Show voltage levels for Transformer-03"  run_id=r_b69bd1fbae
- 1a: page=individual-feeder-meter-shell/voltage-current (metric=voltage), class-appropriate for a transformer feeder voltage query
- 1b: how=ambiguous, 2 candidates: 173 GIC-15 PCC-02 (Transformer-03) has_data, 100176 PQM Transformer-3 Incomer (PCC-02) has_data
- VERDICT: **OK (honest picker)** — MFM vs PQM homonym for the same transformer both offered.

### cross_5  "Show voltage for UPS-10"  run_id=r_c94382a4f9
- 1a: page=individual-feeder-meter-shell/voltage-current (voltage is not a UPS-dashboard first-class metric → feeder-shell voltage page is the class-appropriate fallback)
- 1b: how=ambiguous, 2 candidates: 78 GIC-07 UPS-10 has_data, 236 GIC-21 UPS-10 Incomer-4 has_data
- VERDICT: **OK (honest picker)** — both UPS-10 homonyms offered. Routing nuance (feeder-shell not ups-dashboard) is class-appropriate given the voltage metric.

### cross_6  "real-time power and current for Transformer 01"  run_id=r_ab957fb3ac
- 1a: page=individual-feeder-meter-shell/real-time-monitoring (power+current → RTM, class-appropriate)
- 1b: how=ambiguous, 3 candidates: 171 GIC-15 PCC-01 (Transformer-01) has_data, 100174 PQM Transformer-1 Incomer has_data, 306 GIC-29 33KV Main Transformer-1 Feeder (no data)
- VERDICT: **OK (honest picker)** — good recall incl. the no-data 33KV main; none silently rendered.

### cross_7  "energy consumption of Transformer-05 today"  run_id=r_102b506a1f
- 1a: page=individual-feeder-meter-shell/energy-power (metric=energy, class-appropriate)
- 1b: how=ambiguous, 2 candidates: 263 GIC-24 PCC-03 (Transformer-05) has_data, 100178 PQM Transformer-5 Incomer has_data
- VERDICT: **OK (honest picker)** — MFM vs PQM homonym both offered.

### cross_8  "power quality for a spare feeder"  run_id=r_5caef922fc
- 1a: page=individual-feeder-meter-shell/power-quality (metric=thd, class-appropriate)
- 1b: how=ambiguous, ~46 "Spare" candidates surfaced (16 has_data=True listed first, then no-data ones)
- VERDICT: **OK (honest picker)** — generic/unnamed "spare feeder" → whole Spare class as a picker; correctly refuses to arbitrarily pin one spare and pass it off as THE answer. Candidate ordering (has_data first) is a nice touch.

### cross_9  "voltage and current health for AHU-5"  run_id=r_92a2bfb0ae
- 1a: page=individual-feeder-meter-shell/voltage-current (metric=voltage), class=AHU-appropriate feeder shell
- 1b: how=AI CONFIDENT PIN asset=GIC-03-N6-AHU-5 mfm_id=36 basket_cols=34 (unique match — only one AHU-5)
- validate=pass (34/34 cols pass); asset_gate pinned=True → Layer 2
- L2: 4 cards all conform=True fill=live-frontend answerability=full; exec ok=True ×4; RESPONSE rendered=4 blank=0
- Payload REAL-DATA check vs neuract gic_03_n6_ahu_5_p1 @2026-07-05 01:17: DB v_r/y/b_n=244.0/243.2/246.3 v_avg=244.5 i_avg=50 i_neutral=5.0 → card45 summary.value=50.0 sideValue(neutral)=6.08, card43 v phases 243.8/243.2/245.6 summary 244.2. Values track live table within one sample tick (v_y_n=243.2 EXACT). REAL, not seeds.
- Honest-blank leaves: phase `delta`/`deltaText`='—', several stats.value='—' (need a prior-window comparison not in snapshot) = per-LEAF honest-blank, primary values real. rated_capacity_kva=NULL in DB and NO fabricated capacity in payload.
- No NaN, no payload_error, no surviving Storybook seed. VERDICT: **OK (confident pin, real data, honest per-leaf blanks)**.

### CROSS BATCH SUMMARY
- 9/9 correct. 8 legitimate HOMONYM/generic pins → honest picker with full candidate recall (named asset always offered; no live asset's data ever silently rendered as the answer). 1 unique name (AHU-5) → confident pin with verified real data + honest per-leaf blanks.
- DEFECT FAMILIES: none. Zero mis-pin, zero mis-route, zero NaN/seed, zero payload_error, zero whole-card refuse.
- Anti-mis-pin contract HELD on every homonym (DG-03 Jackson, UPS-04/01/10, Transformer-01/03/05, spare feeder).

================================================================================
# FINAL VERIFICATION MATRIX + LOG INVENTORY + BUNDLE  (2026-07-05)
================================================================================

## (1) 18-PAGE × CARD TABLE

| nn | page | run_id | ok/total | routed_ok | DEFECTS (layer + log evidence) | honest gaps (reason) | infra |
|----|------|--------|----------|-----------|--------------------------------|----------------------|-------|
| 01 | panel-overview-shell/real-time-monitoring | r_f9787f915f | 8/8 | ✅ | — | 7,10 leaf active_power/voltage not on panel meter; 9 coverage 4/8; 6,160 nav cards | up |
| 02 | panel-overview-shell/energy-distribution | r_075d05bffb | 2/2 | ✅ | — | 12 Peak kW null (panel meter); 13 incomers+4 dark feeders None, loss/eff em-dash | up |
| 03 | panel-overview-shell/energy-power | r_99879f110d | 3/4 | ✅ | **17** [ems_exec/fill+strip] fab derived-zero: demand Worst-Peak=0/Load-Factor=0 seed while series peaks ~610kW — card_payloads.payload_stripped(17) stats value:0.0 + no roster binding for demand.view.stats | 14 capacity em-dash; 15 marker/LF honest-null; 16 HHF em-dash | up |
| 04 | panel-overview-shell/harmonics-pq | r_a68ae6e694 | 3/5 | ✅ | **23** [emit+strip] fab seed strip.stats.worst {table MFM_034 nonexistent, status danger, 0.0}; **25** [emit+strip] fab roster 10× MFM_0xx + worstCurrent{MFM_033,warning}, honest_blank verdict inconsistent w/ real ai_summary | 23 worstVThd null; 24 no PQ events; 26/27 pres chrome zeros | up |
| 05 | panel-overview-shell/voltage-current | r_b57a82feb3 | 3/5 | ✅ | **19** [emit+strip] fab roster 10× MFM_0xx + worstCurrent{MFM_033,warning}; **21** [emit+strip] fake MFM_0xx table ids + fabricated-zero vAvg/neutralA/iUnbalance (real 412V exists) | 18 event counts 0; 21 4 dark feeders None; 20,22 real | up |
| 06 | individual-feeder-meter-shell/voltage-current | r_aea5abb769 | 3/4 | ✅ | **44** [emit+strip] fab 'Motor start sag' event string + fab-zero maxLine/minLine/Worst-Spread while sibling c46 binds them real (voltage-history roster gap) | 43 ts/Rate-Change em-dash + gauge chrome; 45 gauge chrome | up |
| 07 | individual-feeder-meter-shell/real-time-monitoring | r_82157379cd | 3/3 | ✅ | — | 36 reactiveEnergy/projectedDemand '—' (window delta unobservable) | up |
| 08 | individual-feeder-meter-shell/energy-power | r_bb525a5212 | 1/4 | ✅ | **39** [emit] reactiveEnergyKwh=21993 raw lifetime counter (agg=last) in Today card, real delta=8; **40** [ems_exec/fill] bars+demandBars all-zero despite real active_power (hourlyAverage filled) + seed demand bands; **42** [strip] 5 fab anomaly labels (Welding Overlap etc.) survive | 41 loss/eff leaves (no HV-side meter) | up |
| 09 | individual-feeder-meter-shell/power-quality | r_1bc17049b9 | 0/3 | ✅ | **47** [strip] derived-zero vThd/flicker/crest + fab 'IEEE 519 Fail' badge + 'APF active' on never-measured compliance; **48** [strip] default v-thd view empty hides real i-thd + seed axis labels; **49** [ems_exec/fill+strip] True PF/PF=None despite real PF cols, PF Gap 0.999 wrong (real -2.0), fab verdict strings | 47 V-THD/flicker/crest genuinely unmeasured | up |
| 10 | diesel-generator-asset-dashboard/voltage-current | r_c7938ef357 | 1/4 | ✅ | **66** [strip] fab 'Elevated' status on 0 V; **67** [strip] 12 fab voltage events + 'Motor start sag' on all-zero series; **69** [fab capacity] 'Rated: 131A' with no nameplate (rated_kva empty, source=none) | 66/68 deltas '—' (DG off); 69 series 0 honest-off | up |
| 11 | diesel-generator-asset-dashboard/engine-cooling | r_dd90453138 | 1/3 | ✅ | **61** [strip] fab thermal events (Exhaust over-temp, Coolant high); **62** [strip] fab event (Oil pressure low) — meter has no thermal/oil columns | 60 no 3D model (honest-blank); 61/62 all thermal KPIs '—' | up |
| 12 | diesel-generator-asset-dashboard/fuel-efficiency | r_1f97dfa47f | 2/3 | ✅ | **65** [strip] 2 fab 'Reserve low' fuel events on meter w/ no fuel-level column | 63 all-null (no fuel data); 65 Efficiency/SFC/Load em-dash | up |
| 13 | diesel-generator-asset-dashboard/operations-runtime | r_44796d791a | 1/4 | ✅ | **71** [strip] seed 'peak 77%' survives (also llm_timeout degrade); **70/71/73** [ems_exec/fill] idle-zero real data blanked w/ reason 'Sensor reading below valid range' — fab sensor-fault narrative (no idle-zero cause in reason_template) | 72 reactive col_absent (verified); 70/73 idle-zero blanks (DG idle 0kW flat 17241 rows) | up |
| 14 | transformer-asset-dashboard/tap-rtcc | r_d06f6da969 | 2/4 | ✅ | **79** [strip+fill] 'Motor start sag' seed + fab 240V-nominal bands over real 6.4kV; **81** [emit] fab 'Total Tap count'=10153.4 from active-power proxy (no tap telemetry); **79/81** [fill] real 6.4kV/-1361kW blanked denorm_garbage | 78,80 tap cols col_absent (verified no tap telemetry) | up |
| 15 | transformer-asset-dashboard/thermal-life | r_f3b19721cb | 2/4 | ✅ | **75** [emit+fill] lifeRemainingYears=10151.7 fab (energy integral mislabeled as years); **74** [fill] 'Normal'/'Stable' status on unmeasured thermal metrics; **75** [fill] real power blanked denorm_garbage | 76 thermal col_absent; 77 fully blank no aging telemetry; 74 thermal col_absent (all verified) | up |
| 16 | ups-asset-dashboard/battery-autonomy | r_8cfd3d6cf1 | 2/4 | ✅ | **52** [emit+fill] fab 'Backup time'=231min (energy integral mislabeled) + [strip] 'Inverter' transfer-mode seed; **53** [fill] render real=14 counts chart-chrome as real data, overstates answerability | 50/51 battery/SOC/scores col_absent; 53 data series col_absent (verified no battery cols) | up |
| 17 | ups-asset-dashboard/output-load-capacity | r_e02e4237bf | 0/3 | ✅ | **59** [ems_exec/fill] SEVERE: composite.points=0 while identical bucketed() returns 25 real pts (real V/I/Hz/kW suppressed on validate=PASS); **58** [fill] sparkline retains default 30×0.0 seed vs real ~197kW; **57/58/59** [fill] denorm_garbage 'below valid range' mislabel on real in-range data; **57** loadFactorPct blank likely no-nameplate but mislabeled | — | up |
| 18 | ups-asset-dashboard/source-transfer | r_d7be9457fc | 1/3 | ✅ | **56** [ems_exec/fill] composite.points empty while data real+fetchable (same history-fill defect as p17); **54/56** [fill] denorm_garbage on real V/I/Hz/power; **54** transfer-readiness scores are active-power proxies, all blanked | 55 transfer-count derivation_unbound — accurate honest-blank (no transfer telemetry, verified) | up |

## (2) TOTALS + DEFECT FAMILIES

**Cards:** 71 total across 18 pages. **OK = 38/71 (54%). DEFECT = 33/71.** Misroutes = **0/18** (every page routed to its class-appropriate shell/tab; routed_ok=true ×18). Honest-gaps (PASS, telemetry) = ~30 leaf-level.
Cross-class edge batch (9 prompts): **9/9 correct, 0 defects, 0 mis-pin, 0 mis-route.**

**DEFECT FAMILIES (card ids):**
- **A — Fabrication-by-zero / derived-zero** (real leaf shown as 0/blank, or seed 0.0 unstripped): **17, 21, 47, 40, 58** ; + status-on-no-data 74. Root: card_payloads.payload_stripped numeric seeds (value:0.0) unstripped AND/OR no data_instructions roster binding for that leaf → seed 0.0 served.
- **B — Surviving Storybook seed literals** (string seeds ride into served payload): **23** (MFM_034/danger), **25/19** (10× MFM_0xx + MFM_033), **42** (Welding Overlap +4), **44/79** (Motor start sag), **67** (Motor start sag +12 events), **61** (Exhaust over-temp/Coolant high), **62** (Oil pressure low), **65** (Reserve low), **71** (peak 77%), **52** (Inverter), **66** (Elevated status), **47** (IEEE 519 Fail/APF active). DB-CONFIRMED: payload_stripped still carries 'Motor start sag'→card 44; 'Welding Overlap'→42; 'peak 77%'→71; MFM_033/034→cards 18-27.
- **C — False-blank / mislabeled reason** (real in-range data blanked as 'below valid range'/'sensor fault'): **57, 58, 59** (p17), **54, 56** (p18), **70, 71, 73** (p13 idle-zero), **79, 75** (p14/15 real 6.4kV/power). Root: denorm_garbage reason_template lacks an idle-zero / valid-low cause; SEVERE sub-case = **59, 56** history/bucketed fill returns 0 pts while identical bucketed() call returns 25 real pts.
- **D — Mis-route: NONE** (0/18 + 0/9 cross).
- **E — Legend/unit leak / mislabeled aggregation**: **39** (raw lifetime counter agg=last in Today card), **81** (active-power proxy mislabeled 'Total Tap count'), **52/75** (∫power integral mislabeled minutes/years), **48** (default v-thd view + seed axis labels).
- **F — Emit-timeout degrade**: **71** (llm_timeout → default payload verbatim, drags in seed 'peak 77%').
- **G — Semantic mis-bind**: **49** (PF Gap 0.999 wrong, real -2.0; True PF None despite real cols), **40** (bars zero but hourlyAverage same-column filled), **53** (answerability overstated).

## (3) FRAMES=PAYLOADS GATE + RENDERER COVERAGE
- **frames=payloads gate: PASS.** `grep -l '_frame_' response_r_*.json` = **0** — zero retired `_frame_*` keys survive in any served payload; the morph payload IS the vm/props (payload-direct FE).
- **payload_error scan: PASS.** `grep '"payload_error"' response_r_*.json` (non-null) = **0** — zero payload_error on all 27 runs.
- **Renderer coverage: 70 distinct card_ids served** (5,6,7…81,160) across the 18+cross sweep; every card mounted its REAL CMD_V2 component from payload (0 payload_error, 0 frames, 0 whole-card refuse). Full frontend registry coverage confirmed.

## (4) CROSS-CLASS VERDICT
9/9 correct, ZERO defects. Anti-mis-pin contract HELD on every homonym (DG-03 Jackson, UPS-04/01/10, Transformer-01/03/05, spare feeder): 8 ambiguous/generic references → honest AssetPicker with FULL candidate recall (named asset always offered, no live asset silently rendered); 1 unique name (AHU-5) → confident pin + verified real data + honest per-leaf blanks. 0 mis-pin, 0 mis-route, 0 NaN/seed, 0 payload_error.

## (5) LOG INVENTORY
- `outputs/logs`: **29 pipeline_r_*.jsonl · 31 ai_*.jsonl · 4 failures_*.jsonl · 27 response_r_*.json** (+ ai_pytest*, failures_pytest* test fixtures).
- **Total LLM calls logged: `cat ai_*.jsonl | wc -l` = 313.**
- **Prompt→run_id map (18 pages):** 01=r_f9787f915f, 02=r_075d05bffb, 03=r_99879f110d, 04=r_a68ae6e694, 05=r_b57a82feb3, 06=r_aea5abb769, 07=r_82157379cd, 08=r_bb525a5212, 09=r_1bc17049b9, 10=r_c7938ef357, 11=r_dd90453138, 12=r_1f97dfa47f, 13=r_44796d791a, 14=r_d06f6da969, 15=r_f3b19721cb, 16=r_8cfd3d6cf1, 17=r_e02e4237bf, 18=r_d7be9457fc.
- **Cross (9):** r_ea44a73ed2, r_a280d5c50b, r_c1bb1de592, r_b69bd1fbae, r_c94382a4f9, r_ab957fb3ac, r_102b506a1f, r_5caef922fc, r_92a2bfb0ae.
- **Logging gaps: NONE.** All 18 sweep + all 9 cross run_ids have complete ai_ + pipeline_ + response_ files. (2 extra logs r_c5233cdb99, r_f3c98b0937 = probe/warmup runs, no served page — not a page gap.)

## (6) BUNDLE
- `outputs/fullsweep_unknown/logs/` = **91 files** (all logs copied). `outputs/fullsweep_unknown/notes/` = 10 files. `outputs/fullsweep_unknown/pages/` = **33 files** (v18_01..18 + b-variants + cross_1..9). Bundle root: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/outputs/fullsweep_unknown/`.

## (7) EXPLICIT VERDICT — CONTRACT NOT CERTIFIED
The routing + render-path + honesty-plumbing half of the contract is CERTIFIED; the data-fidelity half is NOT.

**CERTIFIED:** (a) class-correct routing 18/18 + 9/9 cross (0 mis-route, 0 mis-pin, anti-mis-pin picker held on every homonym); (b) payload-direct render — 0 `_frame_` keys, 0 payload_error, 70/70 cards mount their real CMD_V2 component, 0 whole-card refuse; honest-blank-with-reason works per-LEAF (families 01,02,07 + all col_absent/derivation_unbound blanks are clean PASSES and TRUTHFUL vs neuract).

**BLOCKS CERTIFICATION — 33 cards, strictly DEFECT (not infra, not known-open):**
- **Family B (surviving Storybook seed) is the largest blocker** — DB-confirmed unstripped seeds in `cmd_catalog.card_payloads.payload_stripped` ride into served payloads: 'Motor start sag'(44,79,67), 'Welding Overlap'+4(42), fake MFM_0xx tables(19,23,25,+18/20/21/22/24/26/27 latent), 'peak 77%'(71), 'IEEE 519 Fail'/'APF active'(47), 'Elevated'(66), thermal/fuel events(61,62,65), 'Inverter'(52). Fix = strip-layer (payload_stripped must null string+numeric seeds, not just some) + roster must bind every displayed leaf.
- **Family A (fab-by-zero):** 17,21,40,47,58,74 — unstripped 0.0 seeds + missing roster bindings.
- **Family C (false-blank / mislabel):** SEVERE 59,56 (real bucketed data returns 0 pts on a validate=PASS page — a fill regression), plus 54,57,58,70,71,73,75,79 mislabeled 'below valid range' on real in-range/idle-zero data (reason_template gap).
- **Family E/G (mislabeled aggregation / mis-bind):** 39,81,52,75,48,49,40,53.
- **KNOWN-OPEN [nameplate]:** card 69 'Rated: 131A' fabricated-capacity is the class-default nameplate issue already tracked (asset_nameplate dg_1_mfm rated_kva='' source=none) — the still-unseeded FIXED-nameplate item from memory; classify as KNOWN-OPEN not new-defect.
- **INFRA:** none — :5433 OPEN, host healthy, all logs fresh; every defect is reproducible from a DB row or served-payload citation.

**Bottom line:** ZERO mis-routes, ZERO payload_errors, ZERO frame leaks, honest-blank plumbing sound — but 33/71 cards still emit fabricated content (mostly surviving seeds + fab-by-zero + false-blank mislabels). The contract clause "ZERO fabrication — no surviving Storybook seed number/string, no fabricated derived-zero" is VIOLATED. Fix priority per V48 policy: (1) strip-layer completeness in card_payloads (kills family B + half of A), (2) roster binding coverage for every displayed leaf (kills rest of A + C false-blanks), (3) denorm_garbage reason_template add idle-zero/valid-low cause + fix the history/bucketed fill 0-point regression (59,56).

## PREFLIGHT RE-RUN — freshly-rehosted fixed pipeline @ 2026-07-05 (fullsweep_20260705_163218)

### Gate 1 — health + infra + logs freshness
- `curl :8770/api/health` → `{"ok": true, "sb_base": "http://100.90.185.31:6008"}` (OK).
- `:5433` probe → OPEN (neuract reachable; ground-truth cross-checks viable).
- outputs/logs FRESH: per-run logs accumulating (newest pipeline_r_5925021f9c.jsonl / ai_r_5925021f9c.jsonl @ 16:36). host.log shows a completed run r_a68ae6e694 (panel harmonics-pq, 5 cards, RESPONSE rendered=4 partial=4 blank=1). The BrokenPipeError trace in host.log is a CLIENT disconnect (elapsed_ms=203369 → curl timed out before the 203s response landed) at server.py _send, NOT a pipeline defect. VERDICT: PASS.

### Gate 2 — FRAMES=PAYLOADS (no card routes payload THROUGH a socket/frame mapper)
- Grep of host/web/src/cmd/fill/** (+ whole host/web/src/cmd) for `map*SocketToSnapshot|map*ToFrame|assetPageSocket|build*ViewModel(`.
- All `*Socket*`/`mapVoltageCurrentSocketToSnapshot`/`mapTapRtccToFrame` hits are in COMMENTS documenting the RETIRED path. All `assetPageSocket` hits (card-79/81, date-wiring.ts) are `import type { ChartFilterParams }` — TYPE-only (date-picker param vocab), no runtime call.
- 5 non-comment `build*ViewModel(...)` call sites (tap-rtcc/thermal-life/engine-cooling/fuel-efficiency/operations-runtime view-model.ts). Inspected: each feeds the card's OWN CMD_V2 producer an EMPTY typed scaffold (emptyScaffoldFrame/emptyEngineFrame/emptyFuelFrame/emptyOpsSnapshot) ONLY to derive honest-empty CHROME (axes/labels/colours), then blanks every plotted value. REAL render path = `payload.<slice>` read direct → `vm={…}` (regulationVM/activityVM/tapPositionVM read the payload). This IS the sanctioned FRAMES=PAYLOADS pattern, NOT the retired live-frame→mapper path. card-43 confirmed payload-direct (old createInitialVoltageCurrentSnapshot mock fallback DELETED → honestEmptyHealth).
- VERDICT: CLEAN. No offending file:card.

### Gate 3 — RENDERER coverage (18 routable pages)
- Active allow-list = config/available_pages.available_page_keys() = 18 pages (5 panel-overview + 4 feeder + 9 asset). Resolved via cmd_catalog.routable_pages (DB) with the 18-page code-default identical.
- page_layout_cards for the 18 → 70 unique card_ids, ZERO rows with NULL card_id.
- Coverage union: SPECIAL{8,28,60} ∪ COMPONENTS{57 keys} ∪ COMPOSE{5,6,160} ∪ FILL{43 keys across 12 barrels} = ALL 70/70 resolve. MISSING: NONE.
- DUP card_id across the 12 fill barrels: NONE (each barrel's CARDS keys disjoint).
- 7 routable ids resolve ONLY via FILL (last-resort): 61,62,63,64,65,71,73 — the documented no-Storybook-payload DG cards that honest-degrade to CMD_V2's OWN typed-empty view-model. All others resolve via SPECIAL/COMPONENTS/COMPOSE first (registry tier order SPECIAL>COMPONENTS>COMPOSE>FILL).
- VERDICT: CLEAN.

### Gate 4 — /api/frame CONTRACT (date-nav path)
- server.py do_POST `/api/frame` branch (lines 582-602). Request shape (JSON body):
  { exact_metadata (or payload), data_instructions{consumer{endpoint,asset_table,...}}, asset_table (or consumer.asset_table), date_window{range,start,end,sampling}, _default_payload }
  Required: exact_metadata + asset_table (else 400). It re-COMPLETES JUST that one card via ems_exec_run.run_card(exact_metadata, data_instructions, asset_table, db_link=neuract, window) — the SAME executor the page uses, no ws/mfm. Response: {ok, why, endpoint, payload} where payload is display_dash-applied (honest-dash) + roster_stats popped. Errors return 500 with {ok:false,error}.

## PREFLIGHT (read-only gates) — 2026-07-05

### Gate 1 — liveness/freshness: PASS
- `curl /api/health` -> `{"ok": true, "sb_base": "http://100.90.185.31:6008"}`
- `:5433` neuract probe -> OPEN (ground-truth reads available; not infra_down)
- `outputs/logs/` FRESH: per-run jsonl (pipeline_/ai_) written <1min ago, host.log actively growing (35KB, mtime within sweep)

### Gate 2 — FRAMES=PAYLOADS per-card: PASS (with 1 inert dead-path bug noted)
- Grep hits for `map*ToFrame` / `build*ViewModel(` / `assetPageSocket` are ALL guarded: they run only inside `if (frame)` and the host emits `frames={}` EMPTY (server.py:443/502, confirmed in saved pages: top-frames=dict len 0, no card carries a frame). So every card renders PAYLOAD-DIRECT on the /api/run path; the `mapFrame`/`mapTapRtccToFrame`/`buildRailViewModel(mapFrame(frame))` branches are dead-on-normal-path, not payload-routed-through-a-socket. NOT a render defect.
- NOTE (inert bug, date-nav only): `host/web/src/api.ts fetchCardFrame()` returns `body.frame`, but server.py `/api/frame` returns `{payload: ...}` (no `frame` key). So the per-card date re-fetch always resolves `undefined` -> `setFrame` never fires -> date-nav re-fetch is a silent no-op. Does not affect initial render (payload-direct). Flag for date-nav sweep.

### Gate 3 — RENDERER coverage: PASS
- 18 routable_pages (all enabled='t'), 70 distinct card_ids across page_layout_cards.
- registeredCardIds union = COMPONENTS(58) + FILL + COMPOSE(5,6,108,111,115,160) + SPECIAL(8,28,60) = 74.
- UNCOVERED page card_ids: NONE (all 70 resolve). No cross-tier dup collisions (SPECIAL>COMPONENTS>COMPOSE>FILL priority; overlaps empty). Spare registered (not on the 18 pages): 28,108,111,115.
- Within-page card_id dups in page_layout_cards: NONE.

### Gate 4 — /api/frame contract (date-nav path)
- server.py do_POST `/api/frame` request shape: `{ consumer | data_instructions.consumer, exact_metadata | payload(dict), asset_table | consumer.asset_table, date_window, _default_payload? }`. Requires `exact_metadata` + `asset_table` (400 otherwise). Runs `ems_exec_run.run_card(...)` windowed by `_date_window_for(consumer, date_window)`, applies display_dash, RETURNS `{ok, why, endpoint, payload}`.
- MISMATCH with FE client (see Gate 2 note): FE `fetchCardFrame` sends only `{consumer, date_window}` (no exact_metadata/asset_table -> would 400) AND reads `body.frame` (server sends `body.payload`). Date-nav re-fetch is currently non-functional; initial render unaffected.

## BATCH1 (adversarial logged sweep, run 20260705_163218)

### Page 01 | 'real time monitoring for PCC Panel 1' | run r_f9787f915f
- routed=panel-overview-shell/real-time-monitoring == expected. routed_ok=YES.
- 1b: asset=PCC-Panel-1 mfm_id=317 (VERIFIED canonical: neuract.lt_mfm id317='PCC-Panel-1' table pcc_panel_1_feedbacks). class Panel, no mismatch. This is the CURRENT id-space, not the old off-by-one.
- 8 cards, all conform=true fill=live-frontend exec ok. NaN=none, seed numbers=none, no payload_error, no failures logged.
- Card 7 aggregate REAL: supply=824.4kW = UPS 607.4 + GIC-01 217.0 (matches heatmap section totals). quickStats Current Unbal 5.836, Electrical load 1166A real; Voltage '—' honest.
- Card 5 heatmap: 12 feeders, 4 REAL kw / 8 DASH. GROUND-TRUTH VERIFIED: the 8 dashed feeders' meter tables have 0 rows (gic_01_n9_solar_incomer_1_p1, gic_02_n1_solar_incomer_2_p1, all gic-02-* , gic_15_n10_..._sch does not even exist); the 4 real ones (gic_01_n3_ups_01_p1, gic_01_n8_bpdb_01_p1) have 55K+ rows live (max ts 2026-07-05 16:57). Dashes+nulls = HONEST GAPS, not fill defect.
- Note: pcc_panel_1_feedbacks itself is a SCADA control-feedback table (acb/trip/relay/winding-temp cols), 0 rows, no power metrics — the panel-overview correctly aggregates member FEEDER meters, not this table.
- cards_ok=8/8. defects=NONE. honest_gaps: card5 (8 empty-feeder leaves), card7 (Voltage/PeakToday leaf), card9 (denominator).

## BATCH 2 (pages 07-12)

### Page 07 | 'real time monitoring for GIC-01-N3-UPS-01' | run r_82157379cd
- ROUTED: individual-feeder-meter-shell/real-time-monitoring (expected exactly). 1a AI first picked panel-overview-shell/real-time-monitoring, granularity_reconcile corrected to individual (UPS has_feeders=False) -> routed_ok=TRUE.
- ASSET: GIC-01-N3-UPS-01 CL:600KVA mfm_id=11 class=UPS, pinned by AI, no pending. Correct.
- CARDS 3/3 render real components, all conforms=True, fill_source=ems_exec, no payload_error.
  - card 36 Power & Energy (Real-Time): activePower 202.7kW, activeEnergy 232kWh, apparentPower 203.3kVA, reactivePower 10kVAR, projectedDemand 209.2kW ALL REAL. **DEFECT**: reactiveEnergy blanked to '—' with reason "reactive_energy_import_kvarh, reactive_energy_export_kvarh — no valid reading in this window" BUT this is a DISHONEST blank — reactive_energy_import_kvarh has real monotonic data (July m_start=21060 -> now=22148 => this-month delta ~1088 kVARh; 55703 non-null rows). ROOT CAUSE [ems_exec/fill]: ems_exec/derivations/energy.py reactive_energy_this_month_kvarh reads ctx["this_month"], but the executor ems_exec/executor/fill.py line 203 builds ctx with ONLY {row,start_row,end_row,series,name,rated_kw} — it NEVER sets "this_month"/"today"/"this_week" nor reactive_import/reactive_export. So _period_delta -> ctx.get("this_month")=None -> None -> blank. activeEnergy survives ONLY via the ∫power dead-counter fallback (energy_from_power_kwh reads ctx["series"]); reactive has NO fallback. Contract mismatch: energy.py's period-delta fns expect a consumer ctx that fill.py doesn't provide. active import counter here is flat 0 (reversed-CT, export=330368) so the counter delta path is moot for active but the reactive import register DID move.
  - card 37 Voltage Monitor: series 234-237V per phase REAL, avg/max/min REAL, legend REAL. blank leaves (timeLabels=[''], freshness.tone/label/status='', thresholds value=0.0) are the STRIPPED DEFAULT metadata leaves (verified vs card_payloads.payload_stripped byte-identical) — component renders x-axis from sampleTimestamps/timeLabelTimestamps (both populated with real epochs). Honest metadata blanks, NOT data-leaf fabrication. OK.
  - card 38 Current Monitor: series 277-294A per phase REAL, neutral 14.7A REAL, legend REAL. Same stripped-default metadata blanks as 37. OK.
- routed_ok=TRUE, cards_ok=2/3 (card36 reactiveEnergy leaf defect). No infra issue.

## Batch 3 — Page 13 | 'dg operations and runtime for DG-1'
run_id: r_44796d791a (re-POST asset_id=2 DG-1 MFM, class DG match — layer1b class-matched candidates OK)
routed: diesel-generator-asset-dashboard/operations-runtime == expected. routed_ok=TRUE
asset: DG-1 MFM (mfm_id=2, table dg_1_mfm) — GROUND TRUTH: 35 elec cols only; NO runtime/run-hours/starts/breaker/control/availability/mtbf/mttr/reactive-energy columns. active_power_total_kw = 0.0 ALL 57034 rows (DG idle). active_energy_import_kwh = 27727.707 constant, delta=0 (no production).
cards_total=4  cards_ok=1 (card73 honest-blank)
DEFECTS:
- card70 [layer2-emit]: data_instructions.fields declared kind=const value=99.9 for liveOps.service.availability (FABRICATED reliability metric, no availability col), + const ceiling=5000 / warnPct=80 (fabricated nameplate/threshold). Also stateKpis control='Auto' breaker='Closed' fabricated (no cols). ai_ rec card_id=70 fields.
- card71 [layer2-emit]: duty.points[*].runHours bound to column=active_energy_import_kwh, unit='h', label='Run hours per bucket' → 27727.707 kWh counter displayed as 27,727 RUN HOURS (=3.16yr). Run-hours NOT measured; honest behavior = blank '—'. ai_ rec card_id=71 fields[1].
- card72 [layer2-emit]: cells[2].mtbf / cells[3].mttr unmapped → surviving stripped-default 0.0 shown as real reliability (no col). L2 note claimed 'left blank' but shows 0.0 (derived/surviving-zero). active energy=0.0 (real delta) OK, reactive='—' honest OK.
HONEST GAPS (correct): card72 reactive='—' (col absent, verified); card73 honest_blank empty series (DG produced 0 energy/power today — real); card70/71 loadFactorPct blanked (power=0).
infra_down: FALSE

### Page 02 | 'energy and distribution for PCC Panel 1' | run r_075d05bffb
- routed=panel-overview-shell/energy-distribution == expected. routed_ok=YES. 1b PCC-Panel-1 mfm_id=317 (correct). 2 cards (12 KPI+sankey, 13 flow/sankey), both conform, exec ok. No NaN, no payload_error, no failures logged.
- Card 13 HONEST: sources = 4 incomers (solar-1/2, PCC-tf-01/02) all 0-row tables → sourceInput/loss/lossPct/efficiencyPct all '—' (correctly GATED, loss needs source). feederOutputKw=962.1 real. PASS (honest gaps).
- Card 12/13 empty-feeder nodes (gic-02-*, incomers) = null → HONEST (0-row tables, verified page01).
- *** DEFECT (card 12 & 13, layer=ems_exec/fill) ***: sankey shows 0.0 kWh for the 3 UPS feeders (meter-gic-01-n3/n4/n5-ups-01/02/03) that on page01 carried REAL live power (kw 199/204/204). DB ground truth 24h: these tables have active_energy_import_kwh delta=0 but active_energy_export_kwh delta=4705/4716/4719 (reversed-CT wiring; consumption on EXPORT register). The panel-aggregate renderer ems_exec/renderers/panel_aggregate.py L53 `_ENERGY="active_energy_import_kwh"` + L184 `_panel_energy_kwh` sums IMPORT ONLY and does NOT use the reversed-CT `_pick_register` that the same codebase implements in ems_exec/derivations/energy.py L82-103 (whose comment literally cites "UPS-01 import=0, export=311353 → real consumption on EXPORT"). Result = misleading derived-0.0 (should be 4705 or honest-blank), contradicting the code's own line-162 promise "never a fabricated 0". bpdb-01 node=78930 is correct (forward-wired, import moved, DB import_delta=78880).
- honest_gap (card 12): .kpi.value ("Peak kW")=null and .kpi.pf=null — panel_aggregate renderer computes no peak roll-up (grep: no peak/max in renderer). Null (not '—') w/o per-leaf reason; covered by page-level render verdict "partial / some metrics have no live data". Coverage gap, not fabrication.
- cards_ok: 13=ok (honest), 12=DEFECT (0.0 UPS). cards_ok=1/2. defects=[UPS 0.0 energy mis-register]. 

## Batch 3 — Page 14 | 'transformer tap and rtcc for Transformer-01'
run_id: r_d06f6da969 (re-POST asset_id=171 GIC-15-N3-PCC-01 (Transformer-01), class Transformer match — 3 Transformer candidates OK)
routed: transformer-asset-dashboard/tap-rtcc == expected. routed_ok=TRUE
asset: table gic_15_n3_pcc_01_transformer_01_se — GROUND TRUTH: 70 cols, ZERO 'tap' columns; voltage_avg/r_n/y_n/b_n + kpi_voltage_deviation_pct all live (10757 nn, 9388 in last-24h).
NOTE: 1b logged contract_problems=['resolved asset but empty column_basket'] basket_cols=0 despite has_data=true — basket empty but exec still read voltage (soft data-layer inconsistency, not user-visible).
cards_total=4  cards_ok=4 (all render real component; honest-blanks have reasons; no fabrication)
HONEST GAPS (correct, verified by DB): card78 Tap Position (tap_position/optimal_tap absent → all null, no fabricated tap); card80 Recent Tap Changes (rows:[] empty log, tap-change cols absent); card81 Tap Activity (tap_count_* absent → '—'). All tap telemetry genuinely unmeasured by this MFM meter.
SOFT: card79 Voltage Regulation (swap 79→44 Voltage History): voltage series[0..2] REAL (25 buckets), maxY=6566.8/minY=6250.3 REAL — but stats 'Max Deviation' & 'Worst Spread' + expectedMax/Min blanked '—' although kpi_voltage_deviation_pct/phase-V have 9388 in-window nn rows. Either honest statutory-band-needs-nameplate degrade OR a [ems_exec/fill] derived-stat miss. Renders honest '—' with reason (no fabrication) → counted honest_gap, flagged as fill inconsistency.
DEFECTS: none hard (no fabrication, no payload_error, correct routing/component).
infra_down: FALSE

### Page 08 | 'energy and power for GIC-01-N3-UPS-01' | run r_bb525a5212
- ROUTED: individual-feeder-meter-shell/energy-power (expected exactly). routed_ok=TRUE. Asset UPS mfm_id=11 pinned. validation pass 62/62. cards 39-42, all conforms=True, no payload_error.
- CARD 40 Power Energy Analysis: bars active ~185-203kW, reactive ~9.2-9.8kVAR REAL time-series (reversed-CT abs applied -> positive). OK.
- CARD 41 Input vs Output Energy: hvInputKw 210.7, lvOutputKw 210.7, efficiencyPct 96.3 present. lossKwh='—' (derivation_unbound, activePowerLossKwh has no binding) + deltaPct/lossPctOfInput='—' (hv_input_kw/lv_output_kw not measured by a UPS meter). These are HONEST gaps (a UPS is not a 2-winding transformer; no HV/LV input/output legs) WITH reasons. honest_gap OK. (Minor: efficiency/hvInput both 210.7 identical is suspicious but not a fabrication.)
- **CARD 42 Load Anomalies — DEFECT (seed leak, contract d).** Response anomalies[] (25 elements) carry SURVIVING STORYBOOK SEED prose: title='Welding Overlap', label='Welding\nOverlap (+25%)', detail='Welding bay overlapped the press line — demand surged +25%...', occurredAtDate='15 Apr, 2025', occurredAtTime='02:30:12'. Verified these EXACT strings live in cmd_catalog.card_payloads.payload (RAW) for card 42 story ...cards--load-anomalies but are BLANK in payload_stripped. ROOT CAUSE [ems_exec/fill]: layer2/build.py:391 passes _default_payload = dp["payload"] (RAW seed, NOT payload_stripped); the fill's data_instructions only bind data.anomalies[*].value (active_power_total_kw) so ONLY value is overwritten; every sibling prose leaf of the pre-existing raw default element keeps its Storybook seed (fill._graft_seedfree/blank_data_leaves only strips NEWLY-created out-of-range elements + does 'NO narrative scrub'; element[0] pre-exists so _has_path is true and it is never stripped). Also DATA-quality: anomalies[*].value are NEGATIVE (-199.3,-197.2...) — reversed-CT power not abs()'d for the anomaly series (contrast card 40 bars which ARE positive); a 'surge' with value -199 is nonsensical. This is the exact 'surviving Storybook seed' the run header claims is eliminated.
- **CARD 39 Today's Energy — DEFECT (binding).** totalEnergyKwh=231.0 REAL (derived). BUT activeEnergyKwh=0.0 (bound raw active_energy_import_kwh agg=last -> flat import register; real energy is on the reversed-CT EXPORT register active_energy_export_kwh=330368; shows derived-zero) AND reactiveEnergyKwh=22148.0 (bound raw reactive_energy_import_kvarh agg=last -> the RAW LIFETIME CUMULATIVE counter, not a windowed delta; presenting 22148 kVARh lifetime as 'today/period reactive energy' is wrong; windowed this-month delta is ~1088). ROOT CAUSE [layer2-emit]: data_instructions emit kind=raw agg=last on cumulative counter registers instead of a windowed delta/register-picker. energyTargetKwh/progress*Pct/subsidy*=0.0 are stripped-default (no target configured -> honest, noTargetFallback='Target not configured').
- routed_ok=TRUE; cards_ok=2/4 (40,41 ok; 39 binding defect, 42 seed-leak+negative-value defect). No infra issue.

### Page 03 | 'energy and power for PCC Panel 1' | run r_99879f110d
- routed=panel-overview-shell/energy-power == expected. routed_ok=YES. 1b PCC-Panel-1 mfm_id=317. 4 cards (14 Cumulative Energy, 15 Today live power, 16 Energy Consumption Trend, 17 Daily Power Demand). all conform/exec ok. no NaN/payload_error/failures.
- Card 14 PASS: value=78980 kWh, Active 78980 / Reactive 1093 real; capacityValue/target/markerPct='—' HONEST (no panel nameplate — correctly NOT fabricated, contra the old 20000-vs-160 bug); SEC='—' honest (no tonnage).
- Card 15 PASS: value=823 kW, Active 820.5 / Reactive 30.6 real; capacity/marker/LoadFactor='—' honest.
- *** DEFECT (card 16, layer=ems_exec/fill panel_aggregate energy) ***: Energy Consumption Trend legend "UPS: 0 kWh" and points[].ups=0.0 for BOTH days, while bpdp=22380/56560 real. SAME reversed-CT import-only bug as page02 (UPS consumption on active_energy_export_kwh, delta ~4705/day; panel_aggregate.py L53/L184 sums import only). Misleading derived-0.0. bpdb legend 78,940 correct. HHF='—' honest.
- *** DEFECT (card 17, layer=ems_exec/fill demand load-factor) ***: stats Load Factor=0.0% and criticalKw=0.0 while Worst Peak=1011.6kW real and per-feeder demand points real (ups 597.93, bpdp 339.37...). Computed real load factor from the card's OWN 25 demand points = avg 921.9 / peak 1011.6 = 0.911 (91.1%), NOT 0. derivations/power.py load_factor_pct needs ctx.series[active_power_total_kw]; the panel-aggregate feeds it the panel's near-empty active_power_total_kw (pcc_panel_1_feedbacks has no power col) so avg≈0 → 0.0, while worst_peak pulls the rolled series (1011.6). Inconsistent = derived-zero. criticalKw=0.0 likewise suspect.
- Card 17 otherwise strong: real=50/79 leaves, real per-feeder power series; hhf/rated/contracted null = honest (no such meter/nameplate).
- cards_ok: 14 ok, 15 ok, 16 DEFECT, 17 DEFECT. cards_ok=2/4. defects=[UPS energy 0.0 (c16); load-factor/criticalKw 0.0 (c17)].

## Batch 3 — Page 15 | 'transformer thermal life for Transformer-01'
run_id: r_f3b19721cb (re-POST asset_id=171 GIC-15-N3-PCC-01 (Transformer-01), class Transformer)
routed: transformer-asset-dashboard/thermal-life == expected. routed_ok=TRUE
asset: table gic_15_n3_pcc_01_transformer_01_se — GROUND TRUTH: ZERO temperature/thermal/oil/winding/loss/life/aging/hotspot/insulation columns (verified; 'age' matches only volt-AGE/aver-AGE). Entire thermal-life domain UNMEASURED by this MFM.
cards_total=4  cards_ok=1 (card76 only)
HARD FABRICATION DEFECTS [layer2-emit] — proxy substitution into differently-typed slots (render-guarantee did NOT catch these because the proxy column returned real numbers):
- card77 [layer2-emit]: aging.points[*].hotspotPeakC bound column=voltage_avg unit='°C' label='Hotspot Peak Temperature' → 6498°C winding hotspot (voltage 6498V mislabeled; steel melts ~1500°C). Plus agingFactor/legend[1]/points[*].faa bound column=power_factor_total unit='×' → PF 0.997 shown as 'Daily Aging Factor 0.997×'. Cite: response card77 data_instructions.fields.
- card75 [layer2-emit]: lifeCapacity.lifeRemainingYears kind=derived fn=todaysEnergyTotalKwh(active_energy_import_kwh,reactive_energy_import_kvarh) unit='years' → 22321.6 YEARS remaining life (energy kWh counter). Plus lifeBaseYears kind=const value=20.0 (fabricated design-life nameplate). Cite: ai_r_f3b19721cb card_id=75 fields.
- card74 [layer2-emit]: thermalLife.stressPct kind=derived fn=loadFactorPct(active_power_total_kw) → 94.5% shown as thermal 'stress' on a page with ZERO thermal data (load-factor mislabeled as thermal stress). Winding/Oil/Loss temps correctly '—'. stressBorderPct const=100.
HONEST GAPS (correct): card74 Winding/Oil Temp + Loss = '—' (temp cols absent); card76 Thermal Timeline points:[] empty + legend '—' + tempAxis null (all thermal cols absent) — clean honest-blank, no fabrication; card77 lolPct/deltaLolPct null (LOL not measured); card75 deratedKva/deratedLoad/lifeFillPct '—'.
infra_down: FALSE

### Page 09 | 'power quality for GIC-01-N3-UPS-01' | run r_1bc17049b9
- ROUTED: individual-feeder-meter-shell/power-quality (expected exactly). routed_ok=TRUE. UPS mfm_id=11 pinned. validation pass 45/45. cards 47-49 conforms=True no payload_error.
- **CARD 47 Power Quality — DEFECT (fabricated derived-zero, contract d).** REAL: iThd.valuePct=5.53 (thd_compliance_i_avg), h5.valuePct=6.6 (thd_current_r_pct), h7.valuePct=5.9 (thd_current_y_pct). BUT snapshot.vThd.valuePct=0.0, flickerPst.value=0.0, crestFactor.value=0.0. NEURACT: thd_voltage_r/b/y_pct + thd_compliance_v_avg are ALL-NULL (0 non-null) — vThd genuinely unmeasured, so it SHOULD honest-blank '—'/None (stripped default HAS vThd/flicker/crest = None). ROOT CAUSE [layer2-emit]: ai_r_1bc17049b9 card-47 emit exact_metadata AUTHORED snapshot.vThd={valuePct:0.0}, flickerPst={value:0.0}, crestFactor={value:0.0} — the AI overwrote the honest-null default with a fabricated 0.0. Its OWN L2 note says 'V-THD, Crest Factor, Flicker Pst are not measured for this asset and are omitted' — but it did NOT omit them, it emitted 0.0. Renders as '0% V-THD / compliant', a fabricated favorable reading.
- CARD 48 Distortion & Harmonic Profile: views i-thd + v-thd REAL (yMax 8.97, 3 series x 25 pts). h5-h7 view honest-EMPTY (series:[], harmonic_5th/7th_pct all-NULL — legit blank, no fabricated numbers). Minor: v-thd view yMax identical to i-thd (both 8.97) suggests v-thd subview reuses current-THD data (voltage-THD is all-NULL) — a possible mislabel but real data, not a blank/fabrication. OK (real, honest-empty subview).
- **CARD 49 Load Impact & Transformer Stress — DEFECT (fabricated derived-zero + under-binding, contract c+d).** k-stress: K-factor value=null (honest declared gap, derivation_unbound) + series bound to thd_current_r_pct proxy (real). BUT pf-health view: Power Factor=0.0, True PF=0.0, PF Gap=0.0, PF Target=0.0; pf-angle view: Phase angle=0.0. NEURACT: power_factor_total (55734 nn, -0.999..1.000), kpi_true_pf (55733 nn, max 1.007), kpi_displacement_pf (55734 nn), pf_gap_vs_full_load (55733 nn), phase_angle_deg (55734 nn, max 177) ALL have abundant REAL data. ROOT CAUSE [layer2-emit]: data_instructions._emit_gaps marks 19 pf-angle/pf-health slots 'unbound_by_emit' — the AI bound ONLY the k-stress view and left both PF views entirely unbound despite the real columns existing. The unbound slots fall through to stripped-default 0.0 and RENDER as real 'PF 0.0' (not '—'). Real PF data blanked to a fabricated zero.
- routed_ok=TRUE; cards_ok=1/3 (48 ok; 47 fabricated-zero, 49 fabricated-zero+under-binding). No infra issue.

## Batch 3 — Page 16 | 'ups battery and autonomy for GIC-01-N3-UPS-01'
run_id: r_8cfd3d6cf1 (asset_how=AI, resolved DIRECTLY no popup — GIC-01-N3-UPS-01 CL:600KVA, mfm_id=11, class UPS exact-name match)
routed: ups-asset-dashboard/battery-autonomy == expected. routed_ok=TRUE
asset: table gic_01_n3_ups_01_p1 — GROUND TRUTH: 72-col standard power-quality MFM; ZERO battery/SOC/charge/health/autonomy/backup/temperature/DC-bus/score columns. Battery internals UNMETERED (meter is on UPS electrical output only). Correct that battery-autonomy leaves blank for this asset.
cards_total=4  cards_ok=3 (50,52,53)
DEFECTS:
- card51 [layer2-emit + grounding]: (a) batteryHistory.maxY/minY kind=derived fn=loadFactorPct(active_power_total_kw) → 96.1 electrical load-factor injected as the battery-health-SCORE Y-axis domain while all 4 score series are empty (proxy mislabel; stripped default was 0.0). (b) batteryHistory.peak.label='peak temp 35°C' = SURVIVING Storybook seed string (byte-identical to card_payloads.payload_stripped) — a fabricated 35°C battery peak-temp caption that role_scrub did NOT blank (peak.index correctly gapped null, but the static label survived). Cite: response card51 data_instructions.fields + card_payloads stripped peak.label.
HONEST GAPS (correct, DB-verified all cols absent): card50 SOC/Temp/OutV/OutI '—'; card51 all 4 series values:[] empty; card52 score null + Backup-time/Headroom '—' + envelopePct null; card53 all series empty + zones 0.0.
NOTE: 1b contract_problems=['resolved asset but empty column_basket'] — expected here (power meter mapped to battery page → no matching cols; honest empties, not a routing error).
infra_down: FALSE

## Batch 3 — Page 17 | 'ups output load capacity for GIC-01-N3-UPS-01'
run_id: r_e02e4237bf (asset_how=AI direct — GIC-01-N3-UPS-01 CL:600KVA, mfm_id=11, class UPS). basket_cols=46 (real electrical page).
routed: ups-asset-dashboard/output-load-capacity == expected. routed_ok=TRUE
asset: table gic_01_n3_ups_01_p1 — GROUND TRUTH: active_power_total_kw is NEGATIVE (export sign convention; last-24h min -227.6 max -152.7 avg -195.4 kW), apparent_power_total_kva POSITIVE (153-228), power_factor_total = -0.999 (negative, matches export sign). registry_lt_mfm.rated_capacity_kva = '' EMPTY (no real nameplate despite name 'CL:600KVA'). Real V=237, I=280A, freq=49.97Hz present.
cards_total=3  cards_ok=0 (all 3 have derived-metric defects; raw electrical V/A/Hz/kW leaves ARE real)
DEFECTS:
- card58 [ems_exec/fill]: load.sparkline[*].loadPct bound column=active_power_total_kw unit='%' → raw NEGATIVE kW (-195.68, -196.22) shown as '-196% load' (sign+units not normalized to a percentage). averageLoadPct=96.1 (loadFactorPct abs) is internally inconsistent with the -196% sparkline. Cite: response card58 fields.
- card59 [ems_exec/fill]: composite.points[*].label bound column=active_power_total_kw unit='%' → negative raw kW (-199.2, -197.2) as chart LABELS. inputCurrentA/inputVoltageV/bypassFrequencyHz REAL (280A/237V/49.97Hz). Cite: response card59 fields.
- card57 [layer2-emit + nameplate]: all 3 scoreCells via kpiKwLoadPctOfRated(x, nameplate:rated_kva) with rated_kva='' EMPTY → all identical 37.9 (FABRICATED capacity denominator / fallback — the no-fabricated-capacity rule requires honest-blank when nameplate absent). capacityHeadroom=96.1 (loadFactorPct proxy). readyMarkerPct=100 const placeholder. Cite: response card57 fields + registry rated_capacity_kva=''.
HONEST GAPS (correct): card57 deltaLabel null (insight not measured); card59 composite.points[*].readiness null + composite.series absent.
ROOT CAUSE: export-sign active power not abs-normalized for %-derivations + empty nameplate rated_kva not honest-blanked (fabricated 37.9 capacity score). Real raw electrical values are correct.
infra_down: FALSE

### Page 10 | 'dg voltage and current for DG-1' | run r_c7938ef357 (asset_pending -> re-pinned asset_id=2)
- ROUTED: diesel-generator-asset-dashboard/voltage-current (expected exactly). routed_ok=TRUE.
- ASSET: first run asset_pending=True (ambiguous), 2 DG candidates: DG-1 MFM (mfm_id 2) + GIC-28-N1-DG-01 [Jackson] (mfm_id 300), BOTH class DG (correct class-match, no cross-class candidate -> layer1b OK). Re-POSTed asset_id=2 (DG-1 MFM, the exact name match). Pinned DG-1 MFM table=dg_1_mfm has_data=True. validation pass_with_gaps 17/20.
- CONTEXT: DG-1 is a STOPPED genset — NEURACT dg_1_mfm shows ALL voltage (voltage_r/y/b_n, voltage_ln_max/avg, voltage_ll_avg) AND current (current_r/y/b, current_avg, current_min) columns are non-null but FLAT 0.0 (57231 rows, max 0.0, latest row 0.0). A DG that's off genuinely outputs 0V/0A -> the 0.0 values ARE the real meter readings (real-where-the-meter-measures), NOT fabricated derived-zeros.
- CARD 66 Voltage Live Health: phases value=0.0 (real, DG off), summary L-L avg=0.0, nominal=11.0kV (nameplate), deviation='—' (honest — voltage_avg flat-zero so voltageStatutoryBand can't compute a band; declared gap). OK (honest).
- CARD 67 Voltage History: real=79 (0.0 history, DG off), swap applied, deviation/maxY blanked honest ('voltage_avg not measured' — literal voltage_avg absent; voltage_ln_avg exists but is flat 0.0). OK (honest).
- CARD 68 Current Live Health: Avg=0.0/Neutral=0.0 (real, DG off), Unbalance='—'. conforms=False + payload_error "fields[5] column 'current_unbalance_pct' failed pre-L2 data validation (null_rate 1.00>0.5) — leaf honest-blanks". NEURACT confirms current_unbalance_pct is 0 non-null (all NULL) -> honest-blank is CORRECT. The payload_error is a per-LEAF honest-blank annotation (card still has_payload=True, renders, fill_ok=True) NOT a render failure; page errors={}. Treat as honest_gap.
- CARD 69 Current History: real=79 (0.0, DG off). current_unbalance_pct blanked (all-null, honest) + minY blanked (current_min derivation_unbound — note current_min column EXISTS but is flat 0.0 so no usable value anyway). OK (honest).
- routed_ok=TRUE; cards_ok=4/4 (all render real DG-off state with honest '—' for genuinely-null/flat metrics; card 68 payload_error is honest per-leaf annotation, DB-confirmed). No fabrication. No infra issue.

### Page 04 | 'harmonics and power quality for PCC Panel 1' | run r_a68ae6e694
- routed=panel-overview-shell/harmonics-pq == expected. routed_ok=YES. 1b PCC-Panel-1 mfm_id=317. 5 cards; card 24 L2-SWAPPED to render_card_id=20 (Harmonics&PQ Timeline) — a legit swap, conforms. no NaN/payload_error/failures.
- Real PQ present: iThd 5.27/4.23/3.7/1.23, kw 207.3, pf 0.999, neutralA 18.4, amps 292, vAvg 236.9, iUnbalance 3.77 — VERIFIED real (thd_current_r/y/b 3518/3518 non-null 24h; latest thd_i_r=5.2).
- HONEST GAPS (verified): V-THD null everywhere = thd_voltage_r/y/b 0/3518 non-null (col exists, never logged). h3 null = NO 3rd-harmonic column exists at all. Card 25 AI Summary render=honest_blank "No data logged" (over-conservative but honest, not fabrication). Card 26 Feeder PQ table h3/h5/h7 = null/null/null = CORRECT honest blank (harmonic_5th_pct/harmonic_7th_pct 0-non-null across ALL 4 members).
- *** DEFECT — FABRICATION (card 27 Signature radar, layer=ems_exec/fill) ***: h5=[6.0,4.6,3.7,1.4] h7=[6.0,4.6,3.7,1.4] per feeder, while DB harmonic_5th_pct/harmonic_7th_pct = 100% NULL (0 non-null / 48h, no max) across every panel-1 member. Not a seed (stripped seed = h5:0.0). Not from the derivation registry (NO h5/h7 binding; power_quality.py L3 documents per-order harmonics as "impossible"). h5==h7 identically per row and both track iThd → a synthesized I-THD proxy presented as measured harmonic %. SAME-PAGE PROOF: card 26 honestly nulls the identical leaves from identical data. Contract(d) violation. (h3=null in c27 is honest.)
- cards_ok: 23 ok(honest zeros/nulls verified), 24 ok(swap, real), 25 ok(honest_blank), 26 ok(honest), 27 DEFECT(h5/h7 fabrication). cards_ok=4/5. defects=[c27 h5/h7 synthesized harmonics].

## Batch 3 — Page 18 | 'ups source transfer for GIC-01-N3-UPS-01'
run_id: r_d7be9457fc (asset_how=AI direct — GIC-01-N3-UPS-01 CL:600KVA, mfm_id=11, class UPS). basket_cols=50.
routed: ups-asset-dashboard/source-transfer == expected. routed_ok=TRUE
asset: table gic_01_n3_ups_01_p1 — GROUND TRUTH: ZERO transfer/source/sync/permissive/bypass/mode/readiness/input columns (only generic sag/swell/imbalance event flags). Source-transfer domain entirely UNMEASURED. Real V=237, I=280A, freq=49.97Hz present. active_power negative (export sign).
cards_total=3  cards_ok=0 (all fabricate transfer-domain metrics; raw V/A/Hz leaves in card56 are real)
DEFECTS:
- card55 [layer2-emit] EGREGIOUS: every activity metric bound to fn=activeEnergyTodayKwh(active_energy_import_kwh) → SAME energy value 4707.1 stuffed into 'Last Transfer 4707.1 days ago' (=12.9yr), 'Lifetime Transfers 4707.1' (fractional count), 'count30d 4707.1', lastTransferDays, lifetimeTransfers. One energy counter mislabeled 5 ways as transfer history. Plus fabricated ticks[] (transfer marks at idx 7,24). Cite: response card55 data_instructions.fields.
- card54 [layer2-emit]: readiness score + Input/Bypass/Sync scores ALL identical 96.3 (load-factor proxy for 3 distinct permissive scores that have no columns); deltaLabel=96.3. Cite: L2 note 'load factor as proxy for transfer readiness scores'.
- card56 [ems_exec/fill]: composite.points[*].readiness = NEGATIVE raw active_power (-199.08, -197.2) mislabeled as readiness score. inputCurrentA/inputVoltageV/bypassFrequencyHz REAL (280A/237V/49.97Hz). Mode/series/axes correctly gapped column_absent.
HONEST GAPS (correct): card56 label null + Mode/composite.series/leftAxis/rightAxis all column_absent '—'.
infra_down: FALSE

### Page 05 | 'voltage and current for PCC Panel 1' | run r_b57a82feb3
- routed=panel-overview-shell/voltage-current == expected. routed_ok=YES. 1b PCC-Panel-1 mfm_id=317. 5 cards (18 Events KPI strip, 19 AI Summary, 20 Event Timeline, 21 Current Distribution, 22 Other Panels table). all conform/exec ok. no NaN/payload_error/failures.
- Real V/I present + VERIFIED: amps 280/283/264, vAvg 238.5, vMax 240.5, vMin 237.2, neutralA 14.7, iUnbalance 3.21, iThd 2.17, truePf 0.984 (cards 20/21/22). bpdb-01 current_avg=170 (r186/y149/b175) real.
- HONEST GAPS: card21 panels[4-7] amps/current=null = the 4 empty gic-02-* feeders (0-row, verified p01). card19 AI Summary render=honest_blank "No data logged" (over-conservative like p04-c25; honest, not fabrication).
- *** DEFECT (card 18 Events KPI Strip, layer=ems_exec/fill) ***: strip.stats.worstCurrent for feeder bpdb-01 (mfmId 16, table gic_01_n8_bpdb_01_p1, status:success) fills iThd 2.17 / neutralA 58.6 / iUnbalance 14.77 / truePf 0.984 / vDeviation -0.65 — but amps=null AND current=null, while DB has real current_avg=170A live. The worst-CURRENT feeder rendering its headline amps blank is a fill-coverage defect (the picker resolved the row + read other cols but dropped the amps/current leaf). vAvg/vMax/vMin/sag/swell null there = plausibly honest (bpdb voltage present elsewhere, but this worst-current obj may intentionally omit V).
- Softer note (card 21, NOT counted defect): panels[].vAvg/vMax/vMin/sag/swell=0.0 for the REAL feeders while amps/current real — a current-distribution card; the 0.0 voltage leaves appear to be unused-by-render placeholder zeros (real voltage exists on sibling cards). Watch if these render.
- cards_ok: 18 DEFECT, 19 ok(honest_blank), 20 ok, 21 ok(current real; V zeros unused), 22 ok. cards_ok=4/5. defects=[c18 worstCurrent amps/current null despite real 170A].

### Page 11 | 'dg engine and cooling for DG-1' | run r_dd90453138 (asset_pending -> re-pinned asset_id=2)
- ROUTED: diesel-generator-asset-dashboard/engine-cooling (expected exactly). routed_ok=TRUE. Same 2 DG candidates, re-pinned DG-1 MFM (mfm_id 2, table dg_1_mfm). validation pass_with_gaps 28/33.
- CONTEXT: dg_1_mfm is an ELECTRICAL meter — it has NO engine-diagnostic columns (verified: no oil/temp/rpm/speed/coolant columns exist; only frequency_hz + power/current/energy). And the DG is OFF (active_power_total_kw flat 0.0, frequency_hz flat 0.0). It HAS accumulated energy (active_energy_import_kwh max 27727.7 -> it ran historically). So an engine/cooling page against this meter is INHERENTLY mostly honest-blank.
- CARD 60 Engine 3D Callout Viewer: object=null, viewer={} -> verdict honest_blank. ROOT CAUSE is DOCUMENTED honest-degrade (ems_exec/renderers/asset_3d.py docstring L13-15): neuract asset_3d_model table is EMPTY (verified 0 rows) + every asset.*_asset_3d_id FK null -> resolver binds nothing -> object=null -> FE renders its own ComingSoon3D placeholder, NEVER a fabricated GLB. (A diesel-generator GLB DOES exist in cmd_catalog.asset_3d_registry but the resolver reads NEURACT-only, which is unseeded.) has_payload=True, renders. HONEST GAP (data-seeding gap, not a pipeline fabrication).
- CARD 61 Thermal Timeline: engine-temp chart.series honest-blank ('not measured by this meter' — no temp column); electrical proxy series (active_power_total_kw/frequency_hz/current_avg/power_factor_total) all 'no valid reading in this window' because the DG is off (flat 0.0) + power_factor_total is all-null. real=10 (axis/threshold chrome). Renders empty timeline + honest gaps. HONEST.
- CARD 62 Pressure·Speed·Load: Oil P / Min Oil-P / Speed / Load / Oil Pressure Event Count all 'not measured by this meter' — VERIFIED no such columns on dg_1_mfm (honest-blank correct). active_power kpi 'no valid reading' (DG off). real=36 leaves are axis domains/threshold lines/widths (chrome), NOT measured data. Renders scaffold + honest gaps. HONEST.
- routed_ok=TRUE; cards_ok=3/3 (all honest-blank-per-leaf with reasons; 3D object null = documented neuract-unseeded honest-degrade; no fabrication, page errors={}). honest_gaps: card60 (3D unseeded), card61 (engine temp + DG-off electrical), card62 (no engine sensors). No infra issue.

### Page 12 | 'dg fuel efficiency for DG-1' | run r_1f97dfa47f (asset_pending -> re-pinned asset_id=2)
- ROUTED: diesel-generator-asset-dashboard/fuel-efficiency (expected exactly). routed_ok=TRUE. Same 2 DG candidates, re-pinned DG-1 MFM (mfm_id 2). validation verdict=FAIL n_columns=0 (honest: the meter has no fuel columns) BUT pipeline did NOT refuse — all 3 cards rendered with honest-blanks (correct per-LEAF-not-per-CARD degrade). data_unavailable=False, degrade=None, page errors={}.
- CONTEXT: dg_1_mfm has ZERO fuel/tank/run/start/SFC columns (verified query returns empty) -> every fuel metric is inherently honest-blank.
- CARD 63 Fuel Tank Anatomy: verdict=render, real=0/data=0/undeclared=0 — pure tank-geometry/metadata card (snapshot+display keys), no data leaves. Renders shell. OK.
- CARD 64 All Runs (Fuel Log): real=3, honest gaps 'Faults not measured', 'Starts not measured' (no such columns) + 'active_power no valid reading' (DG off). HONEST.
- CARD 65 Fuel & Tank Composite: legend Level/Rate/Temp='—', kpis Efficiency/SFC/Load='—', series 0-length — all honest-blank ('dg_fuel_level_pct/burn_rate_lph/temperature_c not measured', verified no columns). real=30 = axis/chrome only. **MINOR DEFECT [layer2-emit]**: chart.kpis[2] Cost renders value=0.0 (data_instructions field kind=const metric=dg_cost_per_kwh value:0.0 source=$ctx) — a fabricated derived-zero, NOT declared as a gap, inconsistent with sibling KPIs that correctly blank to '—'. A 'Cost 0.0 /kWh' reading is misleading for an unmeasurable cost. Contract d micro-violation (isolated).
- routed_ok=TRUE; cards_ok=2/3 (63,64 ok/honest; 65 mostly-honest but Cost KPI fabricated-zero). honest_gaps: card64 (faults/starts), card65 (fuel level/rate/temp/eff/sfc). No infra issue.

### Page 06 | 'voltage and current for GIC-01-N3-UPS-01' | run r_aea5abb769
- routed=individual-feeder-meter-shell/voltage-current == expected. routed_ok=YES. 1b asset=GIC-01-N3-UPS-01 CL:600KVA mfm_id=11 class=UPS class_mismatch=False (CORRECT single-asset, NOT a Panel; no asset_pending, no candidates). has_data=true table gic_01_n3_ups_01_p1. SINGLE-ASSET path (not aggregate).
- 4 cards (43 Voltage Live Health, 44 Voltage History, 45 Current Live Health, 46 Current History) all conform/exec ok, rendered 4/4. no NaN/payload_error/failures.
- Real V/I VERIFIED vs DB: card43 phases 237.8/236.4/240.5 summary 238.23 ~ DB voltage_avg 238.3. card45 current 267/257/278 summary 268 ~ DB i_r/y/b 278/269/289 i_avg 279 (windowed vs instantaneous, normal). card44 series 25 real pts maxY 240.88 minY 227.38. card46 series real, stats 203.5/268/4.10/18.19. CURRENT cards 45/46 clean incl "Max gap"=278A real.
- HONEST OK: phases[].delta='—' (no baseline period) honest. band labels -10..+10% present.
- *** DEFECT (cards 43 & 44 voltage-health/history, layer=ems_exec/fill+validate) ***: voltage deviation/spread ANALYTICS leaves honestly-blanked despite REAL data in the rendered window. card44 "Max Deviation"='—' + "Worst Spread"='—'; card43 band.markerPct=null + phase markerPct=0.0 + "Max gap"='—' + "Rate Change"='—'. render reason CLAIMS "voltage_avg, kpi_voltage_deviation_pct — no valid reading in this window" — but DB has kpi_voltage_deviation_pct 3519/3519 non-null (max 0.056), voltage_r/y/b_deviation_pct 3519 non-null (−6.4..+0.83), voltage_max/min real, over the SAME last-24h window in which the card's OWN 25-pt series + voltage_avg 238.23 DID fill. ASYMMETRY PROOF: sibling CURRENT cards 45/46 computed the analogous "Max gap"=278A. So the voltage deviation derivations (voltage.py worst_v_dev etc.) aren't being fed the real column → false "no valid reading" → missed-real defect (contract c: should be real, not blank).
- Soft: card46 expectedMax/expectedMin=0.0 (no nameplate expected band → should be '—' not 0.0; minor derived-zero, not counted).
- cards_ok: 43 DEFECT, 44 DEFECT, 45 ok, 46 ok. cards_ok=2/4. defects=[voltage deviation/spread/band leaves false 'no valid reading' despite 3519 real DB pts (c43,c44)].

## BATCH1 SUMMARY
- ALL 6 pages routed CORRECTLY (verbatim page-key match; 1b class-correct incl UPS single-asset vs Panel aggregate). Zero routing defects. Zero infra_down. Zero NaN / payload_error / literal-NaN. No surviving Storybook seed numbers found.
- Recurring DEFECT THEMES: (1) reversed-CT UPS ENERGY roll-up shows 0.0 (panel_aggregate.py import-only; ignores its own _pick_register export logic) — p02 c12/c13, p03 c16. (2) load-factor/criticalKw derived-0.0 vs real 91.1% — p03 c17. (3) card 27 h5/h7 FABRICATED harmonics (6.0/4.6/3.7/1.4) vs 100%-NULL DB (card 26 honestly nulls same) — p04. (4) worst-current amps null despite 170A real — p05 c18. (5) voltage deviation/spread analytics false 'no valid reading' vs 3519 real pts — p06 c43/c44.
- Panel-overview pages DO render real aggregate data now (contra the old 0/24 dead-end) — the empty PCC device table is correctly bypassed for member-feeder aggregation; empty gic-02-* / solar-incomer / pcc-transformer feeders honestly blank (verified 0-row tables).

---

## CROSS-CLASS / EDGE PROMPT BATCH (9 prompts) — verified 20260705

Runs curled against host :8770; responses in outputs/fullsweep_20260705_163218/pages/cross_<i>.json; stage trace in host.log + outputs/logs/{pipeline,ai}_<run_id>.jsonl.

Ground truth pulled from cmd_catalog.registry_lt_mfm + canonical data.registry.lt_mfm.registry_rows (328 rows; 8 PQM meters at id>=100000 are REAL canonical power-quality meters, tables exist+wired — NOT fabricated).

| # | prompt | run_id | verdict | outcome |
|---|--------|--------|---------|---------|
| 1 | Real-time power of DG-03 Jackson | r_ea44a73ed2 | OK (picker) | asset_pending, 2 cands [4 DG-3 legacy, 302 DG-03 Jackson]; route=DgAssetDashboard/operations-runtime. Recall OK. NOTE: "Jackson" uniquely = id302; name-collision gate (DG-3 vs DG-03 token) fired a picker instead of a confident pin — SAFE but a precision miss. |
| 2 | Load profile of UPS-04 over last 24h | r_a280d5c50b | OK (picker) | asset_pending, 3 real UPS-04 [23,191,299]; route=ups-asset-dashboard/output-load-capacity, intent=trend. Recall OK. |
| 3 | UPS-01 load percentage right now | r_c1bb1de592 | OK (picker) | asset_pending, 5 real UPS-01 [11,188,192,194,296]; route=ups-asset-dashboard/output-load-capacity, intent=snapshot. Recall OK. |
| 4 | Show voltage levels for Transformer-03 | r_b69bd1fbae | OK (picker) | asset_pending, 2 cands [173 live _se, 100176 PQM Transformer-3]. AI (ai_ call#0) returned confident single pin=173; deterministic name-collision gate correctly expanded to picker (2 REAL meters on same PCC-02 xfmr). route=individual-feeder-meter-shell/voltage-current. Recall OK. |
| 5 | Show voltage for UPS-10 | r_c94382a4f9 | OK (picker) | asset_pending, 2 real UPS-10 [78,236]; route=feeder-meter/voltage-current. Recall OK. |
| 6 | real-time power and current for Transformer 01 | r_ab957fb3ac | OK (picker) | asset_pending, 3 cands [171 live _se, 100174 PQM, 306 33KV Main Xfmr-1 Feeder]; route=feeder-meter/real-time-monitoring. Recall OK. NOTE: id306 is a looser "Transformer-1 feeder" match (mild over-inclusion, not a defect). |
| 7 | energy consumption of Transformer-05 today | r_102b506a1f | OK (picker) | asset_pending, 2 cands [263, 100178 PQM]; route=feeder-meter/energy-power, metric=energy. Recall OK. |
| 8 | power quality for a spare feeder | r_5caef922fc | OK (picker) | asset_pending, 46 Spare cands (generic — "a spare feeder" names no unit); route=feeder-meter/power-quality, metric=thd. Correct honest ambiguity. |
| 9 | voltage and current health for AHU-5 | r_92a2bfb0ae | OK (full render) | confident pin id=36 AHU-5 (single match); route=feeder-meter/voltage-current; validation pass 34/34; 4 cards all fill_ok=True, conforms=True, no payload_error; honest-blank leaves each carry a per-LEAF reason (voltage_avg "no valid reading in this window"; ts "column_absent — not measured by this meter"). Real-where-measured, zero fabrication. |

### DEFECT FAMILIES
- NONE. Zero mis-pins, zero mis-routes, zero wrong-live-asset-as-answer, zero dropped intended candidate, zero NaN/Infinity/seed/payload_error.

### KEY VERIFICATION POINTS
- HOMONYM SAFETY (F5/F6): every multi-match prompt surfaced a picker (asset_pending), NEVER silently rendered a different live asset's data. Confirmed the AI can pin confidently (Transformer-03 ai_ call#0 = single name) yet the deterministic name-collision gate (asset_resolve.py L121-129, colliding_rows on the class+unit token) overrides to a picker — intended fabricated-certainty guard.
- CANDIDATE RECALL: 100% — the intended asset id is present in every picker (checked vs registry ground truth).
- PQM candidates (100174/100176/100178) are REAL canonical meters (registry_rows: tables exist, wired), so offering PQM + switchgear meter for one transformer is correct disambiguation, not fabrication.
- HONEST-BLANK: AHU-5 full render degrades PER-LEAF with a reason (telemetry), never whole-card refuse; validation pass.

### SUB-OPTIMAL (observations, not defects — a picker is always contract-safe)
- #1: "DG-03 Jackson" carries a unique disambiguator ("Jackson"=id302) yet the DG-3/DG-03 token collision forces a picker. Ideal = confident pin. The gate is deterministic on the token, blind to the "Jackson" free-text — a possible future precision refinement.
- #6: id306 (33KV Main Transformer-1 Feeder) is a loose match to "Transformer 01"; harmless over-inclusion in the picker.

---

# FINAL VERIFICATION MATRIX — V48 18-page + cross-class certification (2026-07-05)

Infra: host :8770 `/api/health` `{ok:true, sb_base:http://100.90.185.31:6008}`; neuract :5433 OPEN. Verification-only (no restart, no code edits).

## (1) 18-page × card table

| nn | page (route/tab) | run_id | cards ok/total | routed_ok | DEFECTS (card:layer — log evidence) | HONEST gaps (reason) | infra |
|----|------------------|--------|----------------|-----------|-------------------------------------|----------------------|-------|
| 01 | panel-overview/real-time-monitoring | r_f9787f915f | 8/8 | yes | — | c5 8 empty-feeder kw/pf/kva (0-row tables); c7 Voltage+PeakToday; c9 supply denom | ok |
| 02 | panel-overview/energy-distribution | r_075d05bffb | 1/2 | yes | c12:ems_exec/fill — UPS sankey 0.0 kWh, import-only roll-up bypasses reversed-CT export (panel_aggregate.py L53/L184 _ENERGY import-only) | c13 source incomers empty→loss/eff gated; c12 kpi peak/pf null | ok |
| 03 | panel-overview/energy-power | r_99879f110d | 2/4 | yes | c16:ems_exec/fill — UPS trend 0 kWh (import-only reversed-CT); c17:ems_exec/fill — LoadFactor 0.0%+criticalKw 0.0 vs real 91.1% (derived-zero) | c14/c15 capacity/marker/SEC (no nameplate); c17 hhf/rated/contracted | ok |
| 04 | panel-overview/harmonics-pq | r_a68ae6e694 | 4/5 | yes | c27:ems_exec/fill — h5/h7 radar synthesized 6.0/4.6/3.7/1.4 vs 100% NULL harmonic_5th/7th_pct (card26 nulls same leaves) | c23/24/26 V-THD null (never logged); c25 AI summary honest-blank; h3 null | ok |
| 05 | panel-overview/voltage-current | r_b57a82feb3 | 4/5 | yes | c18:ems_exec/fill — worstCurrent amps/current null despite DB current_avg=170A (card21 shows same feeder 264A) | c19 AI summary honest-blank; c21 empty gic-02 feeders null | ok |
| 06 | feeder-meter/voltage-current | r_aea5abb769 | 2/4 | yes | c43:ems_exec/fill — band marker+Max gap+Rate Change false "no valid reading" vs 3519/3519 kpi_voltage_deviation_pct; c44:ems_exec/fill — Max Deviation+Worst Spread blanked despite real in-window data | c43/45 phase delta (no baseline); c46 expected band 0.0 (no nameplate) | ok |
| 07 | feeder-meter/real-time-monitoring | r_82157379cd | 2/3 | yes | c36:ems_exec/fill — reactiveEnergy false-blank vs real ~1088 kVARh (energy.py reads ctx['this_month'] never set by fill.py:203; no reactive fallback) | — | ok |
| 08 | feeder-meter/energy-power | r_bb525a5212 | 2/4 | yes | c42:ems_exec/fill — Storybook seed "Welding Overlap"/"15 Apr 2025" grafted from RAW payload (build.py:391 _default_payload=dp['payload']) + negative reversed-CT; c39:layer2-emit — activeEnergyKwh=0.0 (wrong import register) + reactiveEnergyKwh=22148 (lifetime counter, not windowed) | c41 lossKwh/deltaPct (UPS≠2-winding transformer) | ok |
| 09 | feeder-meter/power-quality | r_1bc17049b9 | 1/3 | yes | c47:layer2-emit — AI authored vThd/flickerPst/crestFactor=0.0 over honest-null (thd_voltage 0 non-null); c49:layer2-emit — 19 pf slots unbound_by_emit→fabricated PF 0.0 vs real power_factor_total 55734 nn | c48 h5-h7 subview empty (all-NULL) | ok |
| 10 | dg-dashboard/voltage-current | r_c7938ef357 | 4/4 | yes | — | all 4: real stopped-DG state (0V/0A real) + honest '—' for null/flat metrics | ok |
| 11 | dg-dashboard/engine-cooling | r_dd90453138 | 3/3 | yes | — | c60 3D model (asset_3d_model unseeded — KNOWN-OPEN seeding); c61 engine-temp+DG-off series; c62 no oil/speed/load sensors | ok |
| 12 | dg-dashboard/fuel-efficiency | r_1f97dfa47f | 2/3 | yes | c65:layer2-emit — Cost KPI const 0.0 (fabricated derived-zero) vs sibling honest-blank (minor contract d) | c64 faults/starts not measured; c65 fuel level/rate/temp/SFC (no fuel columns) | ok |
| 13 | dg-dashboard/operations-runtime | r_44796d791a | 1/4 | yes | c70:layer2-emit — availability=99.9 const+ceiling=5000+warnPct=80+control/breaker strings (no source cols); c71:layer2-emit — active_energy 27727 mislabeled Run Hours (h); c72:layer2-emit — mtbf/mttr surviving 0.0 shown as real | c72 reactive '—' (cols absent); c73 empty energy/power (DG idle) | ok |
| 14 | transformer-dashboard/tap-rtcc | r_d06f6da969 | 4/4 | yes | — | c78/80/81 tap telemetry blank (no tap columns, DB-verified); c79 Max Deviation+Worst Spread '—' (soft fill gap; main voltage series real) | ok |
| 15 | transformer-dashboard/thermal-life | r_f3b19721cb | 1/4 | yes | c77:layer2-emit — voltage_avg 6498V shown as 6498°C hotspot + power_factor 0.997 as Aging Factor; c75:layer2-emit — active_energy 22321 kWh shown as 22321 YEARS + lifeBaseYears=20 const; c74:layer2-emit — loadFactorPct shown as 94.5% thermal stress on all-unmeasured thermal page | c74 Winding/Oil Temp+Loss (cols absent); c76 thermal timeline empty | ok |
| 16 | ups-dashboard/battery-autonomy | r_8cfd3d6cf1 | 3/4 | yes | c51:layer2-emit — loadFactorPct 96.1 as battery-score axis + "peak temp 35°C" surviving Storybook seed (role_scrub miss) | c50 SOC/Temp/OutV/OutI (unmetered); c52/c53 backup/autonomy series empty | ok |
| 17 | ups-dashboard/output-load-capacity | r_e02e4237bf | 0/3 | yes | c57:layer2-emit+nameplate — 37.9 capacity from empty rated_capacity_kva; c58:ems_exec/fill — negative active_power (-196) as '%load'; c59:ems_exec/fill — negative active_power as chart labels | c57 deltaLabel null; c59 readiness null (raw V/A/Hz correct) | ok |
| 18 | ups-dashboard/source-transfer | r_d7be9457fc | 0/3 | yes | c55:layer2-emit — one energy counter 4707 kWh as days-ago+lifetime-count+30d-count; c54:layer2-emit — 3 identical 96.3 load-factor proxies as Input/Bypass/Sync scores; c56:ems_exec/fill — negative active_power as readiness | c56 Mode/composite/axes '—' (raw V/A/Hz correct) | ok |

## (2) TOTALS + defect FAMILIES

Cards OK: **44 / 66** rendered contract-clean (real-or-honest-blank+reason, payload-direct, class-routed).
Routed OK: **18 / 18** pages routed to the exactly-expected class page/tab (zero misroutes).
Honest gaps (non-defect telemetry): ~50 leaves across pages 01,03,04,05,10,11,12,13,14,16 — all carry a per-leaf reason; NONE gate a card render.
DEFECTS: **28** distinct card-level defects across **22 cards** on **12 pages** (pages 02,03,04,05,06,07,08,09,12,13,15,16,17,18). Pages 01,10,11,14 are defect-free.

Defect FAMILIES (card ids):
- **A — fab-by-zero / derived-zero** (real signal exists but a bad register/roll-up yields 0.0 rendered as real): c12, c16, c17 (LoadFactor/criticalKw), c65 (Cost const 0.0). Cross-cuts B/G on the reversed-CT roll-up.
- **B — surviving Storybook seed** (RAW payload prose/number not stripped): c42 ("Welding Overlap"/"15 Apr 2025"), c51 ("peak temp 35°C"). Root: build.py:391 passes `_default_payload=dp['payload']` (RAW not payload_stripped); role_scrub miss.
- **C — false/dishonest blank** (real DB data blanked with "no valid reading"): c36 (reactiveEnergy ~1088 kVARh; ctx['this_month'] never set), c18 (worstCurrent amps vs 170A), c43+c44 (voltage deviation/spread vs 3519/3519 nn). Also c79 (soft — main series real).
- **D — misroute**: **NONE** (0/18).
- **E — legend/unit leak** (unit mislabel / negative-sign not normalized): c58 (−196 as %load), c59 (negative as labels), c56 (negative as readiness), c71 (kWh as "h" run-hours), c77 (V as °C, pf as ×). Sign/units not abs-normalized at fill.
- **F — emit-timeout**: **NONE** (no truncated/timed-out emits; no_retry_kinds held).
- **G — semantic mis-bind** (a real column bound to a slot that does not mean it): c39 (import register + lifetime counter), c47+c49 (AI-authored/unbound PQ zeros), c54+c55 (energy/load-factor as transfer counts), c57 (empty nameplate→fabricated denom), c70 (fabricated availability/breaker consts), c72 (mtbf/mttr), c74+c75+c77 (electrical-as-thermal proxies), c65 (cost const).

Dominant root causes (3 seams carry ~25 of 28 defects):
1. **reversed-CT / register-choice at roll-up** (panel_aggregate.py import-only `_ENERGY`; fill not abs-normalizing export sign): c12,c16,c17,c39,c58,c59,c56,c42(neg).
2. **layer2-emit over-authoring / proxy-substitution on unmeasured slots** (AI binds a real-but-wrong column, or emits a const, into a slot with no measurement source, instead of leaving honest-blank): c47,c49,c54,c55,c57,c70,c71,c72,c74,c75,c77,c65. Concentrated on asset-dashboard pages 13,15,17,18 (UPS transfer/load + transformer thermal-life + DG ops).
3. **period-delta ctx not populated + no fallback** (energy.py period fns read ctx['this_month']/baseline never set by fill.py:203): c36; and derived-stat not fed: c43,c44,c17.
4. **RAW-payload seed not stripped** (build.py:391): c42,c51.

## (3) FRAMES=PAYLOADS gate + renderer coverage (preflight)

- **frames=payloads gate: PASS.** Primary render path is payload-direct: host/web/src/cmd/compose.tsx `COMPOSE: Record<card_id, (payload)=>ReactNode>` mounts each REAL CMD_V2 component from its payload (the payload IS the vm/props; frames retired). The only surviving `mapFrame`/`buildRailViewModel`/`ToFrame` references (RtmComposite.tsx L25-26/62-66/103, compose.tsx L6/20, transformer-tap-rtcc + dg-* view-models) are an **inert dead-path** — they only overlay live heatmap **history** onto an already-payload-rendered RTM card when a live frame exists, else keep the payload seed; they are NOT the render route for any card and never gate a card. Noted, not a render defect.
- **Renderer coverage: PASS.** Every card_id encountered across the 18 pages resolved to a real CMD_V2 component; zero `payload_error` at page level (per-leaf payload_error annotations e.g. p10/c68 are LEAF telemetry with has_payload=true, page errors={}); zero NaN; zero whole-card refuse — every card rendered its real component and degraded per-leaf.

## (4) CROSS-CLASS verdict

7 sweep-adjacent cross prompts (r_ea44a73ed2, r_a280d5c50b, r_c1bb1de592, r_b69bd1fbae, r_c94382a4f9, r_ab957fb3ac, r_102b506a1f) + AHU edge: **ALL OK**. Ambiguous asset names (DG-03/DG-3, UPS-01×5, UPS-04×3, UPS-10×2, Transformer-01/03/05 with live `_se` + PQM + feeder collisions) correctly widened to the AssetPicker with the full real-candidate set (recall complete), each routed to the class-correct page/tab. Two sub-optimal-but-contract-safe observations (not defects): "DG-03 Jackson" free-text disambiguator ignored by the token gate (still safe via picker); id306 33KV feeder loosely included in the Transformer-01 picker. **Cross-class routing/recall CERTIFIED.**

## (5) LOG INVENTORY

- `outputs/logs`: **97 files** = 33 `pipeline_*.jsonl` + 33 `ai_*.jsonl` + 1 `failures_default.jsonl` (+30 other run artifacts).
- Total LLM calls (`cat ai_*.jsonl | wc -l`): **248**.
- `failures_default.jsonl`: 4 recorded lines (recorded gaps; not a crash log).
- Per-page prompt→run_id map (all 18 have BOTH pipeline_ and ai_ logs — **zero logging gaps**):
  - 01 "real time monitoring for PCC Panel 1" → r_f9787f915f
  - 02 "energy and distribution for PCC Panel 1" → r_075d05bffb
  - 03 "energy and power for PCC Panel 1" → r_99879f110d
  - 04 "harmonics and power quality for PCC Panel 1" → r_a68ae6e694
  - 05 "voltage and current for PCC Panel 1" → r_b57a82feb3
  - 06 "voltage and current for GIC-01-N3-UPS-01" → r_aea5abb769
  - 07 "real time monitoring for GIC-01-N3-UPS-01" → r_82157379cd
  - 08 "energy and power for GIC-01-N3-UPS-01" → r_bb525a5212
  - 09 "power quality for GIC-01-N3-UPS-01" → r_1bc17049b9
  - 10 "dg voltage and current for DG-1" → r_c7938ef357
  - 11 "dg engine and cooling for DG-1" → r_dd90453138
  - 12 "dg fuel efficiency for DG-1" → r_1f97dfa47f
  - 13 "dg operations and runtime for DG-1" → r_44796d791a
  - 14 "transformer tap and rtcc for Transformer-01" → r_d06f6da969
  - 15 "transformer thermal life for Transformer-01" → r_f3b19721cb
  - 16 "ups battery and autonomy for GIC-01-N3-UPS-01" → r_8cfd3d6cf1
  - 17 "ups output load capacity for GIC-01-N3-UPS-01" → r_e02e4237bf
  - 18 "ups source transfer for GIC-01-N3-UPS-01" → r_d7be9457fc
  - cross: r_ea44a73ed2, r_a280d5c50b, r_c1bb1de592, r_b69bd1fbae, r_c94382a4f9, r_ab957fb3ac, r_102b506a1f (all pipeline_+ai_ present).
- Missing logs: **NONE** for any of the 18 sweep or 7 cross run_ids.

## (6) BUNDLE

Final bundle: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/outputs/fullsweep_20260705_163218/`
- `logs/` — 97 files (all pipeline_/ai_/failures_ copied)
- `pages/` — 33 files (18 v18_* pages [some with _b full-response variants] + 9 cross_*.json)
- `notes/` — copied
- `host.log` — 109 KB durable stage stream

## (7) EXPLICIT VERDICT

**Contract NOT YET CERTIFIED.** Blocked strictly by DEFECTS (not infra, not honest-gap):

CERTIFIED aspects (hold on all 18 pages + cross):
- (a) class-correct routing: **18/18 + all cross** — zero misroute (family D empty).
- (b) payload-direct render: **PASS** — frames retired, every card mounts its real CMD_V2 component from payload; zero payload_error/NaN/whole-card-refuse; frames=payloads gate PASS.
- honest-blank+reason discipline: **PASS** — ~50 honest gaps all carry a per-leaf reason, none gate a card (pages 01,10,11,14 are fully clean; DG/transformer no-sensor blanks exemplary).

BLOCKING defects (contract c "honest-blank not false-blank" + d "zero fabrication"):
- **28 defects on 22 cards / 12 pages.** Worst-hit: asset-dashboard pages 13,15,17,18 (0-1 cards clean) where layer2-emit over-authors electrical columns / consts into unmeasured thermal/transfer/capacity slots (family G) — c54,c55,c57,c70,c71,c72,c74,c75,c77; and the panel/feeder reversed-CT register roll-up (family A/E/G) — c12,c16,c17,c39,c58,c59,c56.
- Two surviving Storybook seeds (family B): **c42 "Welding Overlap"/"15 Apr 2025", c51 "peak temp 35°C"** — direct contract-d violations, root build.py:391 `_default_payload=dp['payload']` (RAW).
- Dishonest false-blanks (family C): c36 reactiveEnergy, c18 worstCurrent, c43+c44 voltage deviation — real DB data blanked with "no valid reading".

KNOWN-OPEN (not counted against certification, pre-agreed): c60 3D model (neuract asset_3d_model unseeded); nameplate absence driving honest-blanks (c14/c15/c46 etc.) is correct behavior — the only nameplate DEFECT is c57 where an EMPTY rated_capacity_kva was used as a fabricated denominator (should honest-blank).
INFRA: none — neuract :5433 OPEN, host live throughout; no infra_down on any page.

**To certify:** fix the 3 root seams — (1) reversed-CT/register choice + export-sign abs-normalization at panel_aggregate.py/fill (clears ~8 defects), (2) layer2-emit "honest-blank an unmeasured slot instead of authoring a proxy/const" guard on asset-dashboard pages (clears ~12), (3) strip from payload_stripped not RAW at build.py:391 + role_scrub (clears c42,c51), plus (4) populate ctx['this_month']/baseline in fill.py:203 for period-delta derivations (clears c36,c43,c44). Estimated 28→0 with those four fixes; routing + render-path already certified.


---

## PREFLIGHT (read-only gates) — 2026-07-05

**Gate 1 — health/infra/log-freshness: PASS**
- `GET /api/health` -> `{"ok": true, "sb_base": "http://100.90.185.31:6008"}`
- `:5433` probe -> OPEN (neuract ground-truth reachable; NOT infra_down)
- `outputs/logs/` FRESH: run `r_ab957fb3ac` landed 20:34 (response/pipeline/ai jsonl present); host.log updating 20:35. Host live, read-only.

**Gate 2 — FRAMES=PAYLOADS per-card mapper gate: CLEAN (no live defect)**
- Grep across host/web/src flagged 14 files. Classified each:
  - COMMENT-only mentions (mapper path described as DELETED): dg-fuel-efficiency.tsx, panel-overview-voltage-current/card-43.tsx, transformer-tap-rtcc.tsx, transformer-thermal-life.tsx, dg-engine-cooling.tsx.
  - TYPE-ONLY import `import type {ChartFilterParams} from "@cmd-v2/realtime/assetPageSocket"` (no runtime call): transformer-tap-rtcc/{card-79,card-81,date-wiring}.
  - ALLOWED producer reuse `build*ViewModel(...)` fed a SCAFFOLD/empty-frame or the payload (Option-A: payload IS the frame, card's OWN producer builds vm): transformer-thermal-life/view-model.ts, dg-engine-cooling/view-model.ts, dg-operations-runtime/view-model.ts, transformer-tap-rtcc/view-model.ts, dg-fuel-efficiency/view-model.ts.
- ZERO live `map*SocketToSnapshot(` or `map*ToFrame(` CALLS anywhere (grep of `\s*\(` form empty).
- ONE live socket-mapper CALL exists: RtmComposite.tsx L62/L103 `mapFrame(frame)` (imported from `@cmd-v2/.../realTimeMonitoringMapper`), rendered via CardGrid.tsx:66. HOWEVER it is UNREACHABLE: host server.py L443 `frames,frame_status={},{}` and L502 emits `"frames": frames` EMPTY (verified in live response_r_ab957fb3ac.json -> `frames -> {}`). App.tsx:59 passes `frames={result.frames}`={} -> `frameFor` returns undefined -> `liveRailVM(undefined)` returns undefined -> seed/payload wins. DEAD path, not a runtime defect. NOTE for cleanup: the `mapFrame` import + liveRailVM/HeatmapBody live-frame branches in RtmComposite are residual dead code (only fire if `frames` is ever repopulated).

**Gate 3 — RENDERER coverage: CLEAN (70/70 covered, no true dup)**
- 18 routable_pages -> 70 distinct card_ids; NO intra-page dup card_id.
- Every card_id resolves to >=1 render tier: SPECIAL{8,28,60} / COMPONENTS(58 ids) / COMPOSE{5,6,160} / FILL(43 ids). Zero card falls to envelope-shape-only-with-no-tier; zero uncovered.
- COMPONENTS∩FILL overlap = 36 cards = EXPECTED tiering (registry tries SPECIAL->COMPONENTS->COMPOSE->FILL; COMPONENTS is primary, FILL is documented last-resort). Registry only warns on FILL-vs-FILL dup — none (each fill id exported once).

**Gate 4 — /api/frame CONTRACT (date-nav path), server.py L582-602:**
- Request shape (POST JSON): `{ exact_metadata (or payload), data_instructions{consumer{...}}, asset_table (or consumer.asset_table), date_window, _default_payload }`.
- Requires: `exact_metadata` non-null AND `asset_table` non-null (else 400 "exact_metadata + asset_table required").
- Window resolved via `_date_window_for(consumer, date_window)`; re-fills JUST that card via `ems_exec_run.run_card(exact_metadata, data_instructions, asset_table, db_link=neuract_dsn, window)`; strips roster_stats; applies display_dash policy.
- Response: `{ok, why, endpoint: consumer.endpoint, payload}` (payload = re-filled CMD_V2 props). Honest-degrade: exception -> 500 but stripped/shape-complete elsewhere per policy.

## BATCH 3 (pages 13-18) — FRESH RE-HOST adversarial logged sweep — 2026-07-05
Ground truth (neuract, fresh to 2026-07-05 20:40):
- DG-1: mfm_id=2, table dg_1_mfm (35 electrical cols; NO fuel/runtime-hrs/engine-temp/oil/RPM). Latest instantaneous P/I/V=0 (idle) but active_energy_import_kwh=27727.707 real cumulative.
- Transformer-01: mfm_id=171 (Secure Elite300, gic_15_n3_pcc_01_transformer_01_se, 70 cols electrical+THD+events; NO tap/RTCC/winding-temp/oil-temp/thermal-aging). id=164 table_exists=f. Latest P=-766.5kw S=769.5kva PF=.997 Hz=50.01 real; current_avg/voltage_ll_avg NULL in latest row.
- UPS-01 (GIC-01-N3-UPS-01): mfm_id=11, table gic_01_n3_ups_01_p1 (72 cols electrical+harmonics; NO battery-SOC/autonomy/DC-bus/source-transfer). Latest P=-184.4 S=185.1 I=262 V=407 real.

## BATCH 2 (pages 07-12) — FRESH RE-HOST adversarial logged sweep — 2026-07-05
### Page 07 | 'real time monitoring for GIC-01-N3-UPS-01' | run r_82157379cd
- routed=individual-feeder-meter-shell/real-time-monitoring (EXPECTED match). asset=GIC-01-N3-UPS-01 mfm_id=11 class=UPS has_data=true (AI, no candidates). granularity_reconcile note present (panel-overview->individual, correct).
- 3/3 cards OK (36 Power&Energy, 37 Voltage, 38 Current). All conforms=true, fill_source=ems_exec, fill_ok=true, payload_error=null. validate=pass (64/64 cols). NO failures file.
- Real neuract binding CONFIRMED: card38 current series ~264-265 matches live current_avg=265; card36 power series ~194-203 magnitude matches live |P|~184. No NaN, no null leaves, no dash-string leaves.
- Seed check: 0 orig-storybook-seed survivors on cards 36/37; card38 has .data.thresholds[0/1].value=120/100 = band-limit CONFIG (not measured data) → NOT fabrication.
- render.verdict=partial ("some metrics have no live data") on all 3 = honest per-leaf degrade telemetry (real 56/70, 81/86, 84/89) — the missing leaves are non-measured (harmonics/derived) UPS metrics. PASS.

### Page 13 | 'dg operations and runtime for DG-1' → diesel-generator-asset-dashboard/operations-runtime (run r_44796d791a)
- 1st POST asset_pending → 2 DG candidates (mfm_id=2 DG-1 has_data=t; 300 has_data=f). Re-POST asset_id=2 (class-matched DG). routed=operations-runtime shell=DgAssetDashboard class DG. routed_ok=YES.
- GROUND TRUTH dg_1_mfm: active_power_total_kw = 0 across ENTIRE history (max=avg=0) — standby DG, never ran; only active_energy_import_kwh=27727.707 (flat cumulative) + reactive_power_total_kvar. NO reactive_energy_import_kvarh / reactive_energy_export_kvarh / runtime-counter / control-mode / breaker cols.
- 4 cards (70,71,72,73) conform, no payload_error, 3 partial + 1 full.
- card 73 (Power Energy Analysis): config-only (metricTabs/units/labels/constLimit) — no data leaves. OK.
- card 71 (Runtime & Duty): loadPct=null honest; runHours=27727.707 real (flat=idle); starts=0. DEFECT-minor: topKpis average-load sub="peak 77%" survives from seed (seed had peak 77%) — value="—" but the "peak 77%" subtitle is a surviving seed label. layer=[layer2-emit] (exact_metadata kept seed sub). log: v18_13b.json card71 topKpis average-load.sub.
- card 70 (Live Ops & Runtime): DEFECTS — (a) stateKpis Control="Auto" + Breaker="Closed" are surviving Storybook seed STRINGS (present in payload_stripped, un-stripped; dg_1_mfm has NO control/breaker column) → fabricated state chips. (b) topKpis starts=0.0 + total-runs=0.0 unmapped in data_instructions.fields → stay at stripped 0.0 (should be honest-blank "—"; DG has no starts/total-runs counter). Contract (d) fabricated. run-hours=0.0 defensible (bound to active_power_total_kw, real idle). availability="—" honest. layer=[layer2-emit]+[strip]. log: ai_r_44796d791a.jsonl call#9 fields maps only topKpis[0,3]/service/stateKpis[2,3]; Control/Breaker/starts/total-runs UNMAPPED; payload_stripped card70 keeps Control:"Auto"/Breaker:"Closed".
- card 72 (Energy & Reliability): DEFECTS — (a) mtbf + mttr cells NOT in data_instructions.fields → render fabricated 0.0 (should be "—"; DG has no MTBF/MTTR). (b) active/reactive/apparent MWh derivations bound to reactive_energy_import_kvarh & reactive_energy_export_kvarh which DO NOT EXIST in dg_1_mfm → derived fns get no data → fabricated 0.0. Only active_energy_import_kwh exists. Note claims "MTBF/MTTR left blank" but they render 0.0. Contract (d) fabricated derived-zero + wrong-column bind. layer=[layer2-emit]. log: ai_r_44796d791a.jsonl call#10 fields bind cells[0]/[1]/activeMwh/reactiveMvarh to nonexistent reactive_energy_*_kvarh; mtbf/mttr absent from fields; DG cols verified = only active_energy_import_kwh + reactive_power_total_kvar.
- VERDICT page 13: routed_ok. cards_ok=1/4 (73). 70,71,72 = defects (fabricated 0.0 derived-zeros for unmeasured runtime/reliability leaves + surviving Control/Breaker seed + wrong-column energy binds).

### Page 08 | 'energy and power for GIC-01-N3-UPS-01' | run r_bb525a5212
- routed=individual-feeder-meter-shell/energy-power (EXPECTED match). asset=UPS-01 mfm_id=11 (AI). validate=pass 64/64. 4/4 exec ok. NO failures file.
- 4/4 cards OK (39 Today's Energy, 40 Power Energy Analysis[history], 41 Input vs Output Energy, 42 Load Anomalies[history]). All conforms/fill_ok, payload_error=null. Zero orig-storybook-seed survivors on ALL four (39/40/41/42).
- Real binding CONFIRMED: card39 reactiveEnergyKwh=22184 == neuract reactive_energy_import_kvarh max=22184; activeEnergyKwh=0.0 == neuract active_energy_import_kwh=0 (REAL zero — meter logs 0 import); totalEnergyKwh=231 real.
- HONEST-BLANK (card41 Input vs Output Energy): lossKwh/deltaPct/efficiencyPct/lossPctOfInput = '—' WITH reasons ("no derivation binding configured for activePowerLossKwh"; "active_power_total_kw no valid reading in window"). hvInputKw=lvOutputKw=192.4 real (import energy genuinely absent → no true HV/LV split, loss correctly refused not derived-zero). PASS.
- MINOR honest-gap (not a defect): card41 .data.expectedLossKwh=0.0 is the STRIPPED placeholder-zero (orig seed was 1461) — ideally '—' for consistency with lossKwh, but it is NOT a surviving seed and NOT a fabricated measurement. card39 .data.insight='' empty + target/subsidy zeros carry honest 'Target not configured' fallback label.

### Page 14 | 'transformer tap and rtcc for Transformer-01' → transformer-asset-dashboard/tap-rtcc (run r_d06f6da969)
- 1st POST asset_pending → 3 Transformer candidates. Re-POST asset_id=171 (GIC-15-N3-PCC-01 Transformer-01 Secure Elite300, has_data=t, name-match). routed=tap-rtcc shell=TransformerAssetDashboard. routed_ok=YES.
- GROUND TRUTH: gic_15_n3_pcc_01_transformer_01_se has ZERO tap/rtcc/oltc columns (verified). active_power_total_kw = -1551..-631 (avg -929, NEGATIVE incomer). voltage_r_n 6252-6595V real. voltage_ll_avg all NULL.
- 4 cards. card 79 SWAPPED 79→44 (voltage-history).
- card 78 (Tap Position Optimization): honest-blank — current/optimal=null, RTCC mode="", gauge null. No fabrication. OK (honest_gap; nulls clean, though no per-leaf reason string in payload).
- card 80 (Recent Tap Changes): rows=[] empty — honest-blank. OK (honest_gap).
- card 79 (Voltage Regulation Timeline, =card44): REAL voltage series R/Y/B ~6500V matches voltage_r_n 6252-6595 avg 6471; seed maxY=440 overwritten to 6566. No fabrication. OK. (minor: all events index=0.0 — position collapse, not a data-fabrication.)
- card 81 (Tap Activity & Wear): SEVERE DEFECT — every tap-activity leaf (Total Tap count -1122.75 "/5 million left", Peak, Average, points -960..-979, legend, cumAxis/countAxis) bound DIRECTLY to active_power_total_kw (negative incomer power) → renders NEGATIVE "tap counts", physically impossible. No tap column exists → MUST be honest-blank "—", not a power-proxy. Contract (d) fabrication. layer=[layer2-emit]. log: ai_r_d06f6da969.jsonl card81 data_instructions.fields — ALL 12 slots <- active_power_total_kw fn=None; DB tap/rtcc/oltc cols = [] (empty); active_power range -1551..-631 confirmed.
- VERDICT page 14: routed_ok. cards_ok=3/4 (78,79,80). card 81 = severe fabrication (negative tap counts from power proxy). NOTE: card 81 L2 note itself admits "active_power_total_kw is used to represent activity level" — that admission = fabricating a proxy where honest-blank is required.

### Page 15 | 'transformer thermal life for Transformer-01' → transformer-asset-dashboard/thermal-life (run r_f3b19721cb)
- Re-POST asset_id=171. routed=thermal-life. routed_ok=YES.
- GROUND TRUTH: temp/thermal/oil/winding/hotspot/aging/life cols = [] (NONE exist). active_power_total_kw NEGATIVE (latest -776..-830, avg -929).
- 4 cards, all "partial" — but ALL 4 fabricate temperature/aging from active_power_total_kw:
  - card 74 (Thermal Life): DEFECT — "Winding Temp" = 879.00006 °C (=|active power| ~879kW stamped with °C unit; ai_ card74 fields metrics[0]<-active_power_total_kw unit=kW but slot renders °C). stressPct=95 fabricated. Oil Temp="—"/Loss="—" honest but Winding Temp fabricated. Contract (d) — impossible 879°C winding.
  - card 76 (Thermal Timeline): DEFECT — hotspot/oil/winding legend & points ALL = -879 / -923..-979 °C (NEGATIVE Celsius from negative power). Load/Efficiency also -879. Impossible negative temps. Contract (d).
  - card 75 (Life & Capacity): DEFECT — lifeFillPct/lifeRemainingYears/deratedFillPct/deratedLoadKva all =95 (from active_power stress proxy); lifeRemainingYears=95yrs fabricated. deratedKva=1000 nameplate ok. Contract (d).
  - card 77 (Insulation Aging & Loss of Life): DEFECT — agingFactor/lol/faa/lolPct/hotspotPeakC all -879/-923 (negative from power); lifeUsedPct/deltaLolPct=95. Contract (d).
- ROOT CAUSE (all 4): [layer2-emit] the AI, faced with unmeasured thermal/aging leaves, bound them to active_power_total_kw as a "proxy" instead of honest-blank. Negative incomer power → negative °C / negative aging. log: ai_r_f3b19721cb.jsonl each card's data_instructions.fields <- active_power_total_kw; DB temp/thermal/oil/aging cols=[] empty; active_power latest -776..-830.
- VERDICT page 15: routed_ok. cards_ok=0/4. Systematic power-as-thermal-proxy fabrication; per-leaf honest-blank required.

### Page 09 | 'power quality for GIC-01-N3-UPS-01' | run r_1bc17049b9
- routed=individual-feeder-meter-shell/power-quality metric=thd (EXPECTED match). asset=UPS-01 mfm_id=11 (AI). validate=pass_with_gaps 64/68 (4 fail = voltage-THD cols null). 3/3 exec ok. NO failures file.
- CARD 48 Distortion&Harmonic = OK: binds REAL current-THD (i-thd series ~6-9 matches neuract thd_current 7.7-9.9). v-thd series = arrays of [None,...] (honest null) WITH reason "thd_voltage_r/y/b_pct not logged by this meter" — VERIFIED neuract thd_voltage_r/y/b_pct = 0/300 nonnull (genuinely NULL). MINOR honest-gap: v-thd averageStat.value=0.0 (derived-zero leak, should be '—'; series correctly null; reason present).
- CARD 49 Load Impact&Transformer Stress = OK: 156 nums real, 0 dash/NaN, honest reasons for yTicks/xLabelIndexes (chart-axis metadata, not meter data). swap=keep (PF Health + K-Stress views serve the story).
- CARD 47 Power Quality = **DEFECT [layer2-emit] PROXY-BINDING**: distinct-quantity slots bound to UNRELATED real columns instead of honest-blank — snapshot.crestFactor.value=18.0 <- current_max_spread(=19) [crest factor physically ~1.4, NONSENSE]; snapshot.flickerPst.value=-2.33 <- kpi_voltage_deviation_pct [flicker != voltage deviation]; snapshot.trendPctPerHour=-202.3 <- active_power_total_kw [trend% != raw power]; snapshot.h5/h7.valuePct=6.8/7.2 <- thd_current_r/y_pct [true harmonic_5th/7th_pct are NULL — arguably-defensible family proxy]. Values ARE real neuract (not fabricated seeds), but MISLABELED. Emit DOCUMENTED it in _emit_gaps ("Flicker, Crest Factor, Trend Rate are proxied by available voltage deviation and current spread metrics") + honest-blanked flickerPst.peakToday for column-reuse → machinery exists but chose proxy over '—' for primaries. snapshot.vThd.valuePct=0.0 also derived-zero (should be '—').

### Page 16 | 'ups battery and autonomy for GIC-01-N3-UPS-01' → ups-asset-dashboard/battery-autonomy (run r_8cfd3d6cf1)
- Pinned directly (how=AI, prompt named exact asset) mfm_id=11 UPS. routed=battery-autonomy. routed_ok=YES.
- GROUND TRUTH: gic_01_n3_ups_01_p1 battery/soc/autonomy/dc/temp cols = [] (NONE). V/I real (voltage_avg~235, current_avg~283-292). active_power NEGATIVE -184..-204.
- 4 cards, all partial:
  - card 50 (Battery Health): MIXED. soc=0.0 socPct="—" honest-blank (good). Output Voltage=234.93V REAL (matches voltage_r_n~234.6), Output Current=263A REAL (current_avg range). DEFECT: Temperature=0.0 °C fabricated (no temp col → should be "—"). Otherwise the real electrical leaves are correct.
  - card 51 (Battery Health History): DEFECTS — (a) series/maxY/minY = -185..-204 (negative active power rendered as battery "Score") → negative battery scores, fabrication. (b) SURVIVING SEED peak.label="peak temp 35°C" (present in payload_stripped un-stripped; no temp source). Contract (d). log: card_payloads.payload_stripped card51 keeps "peak temp 35°C"; ai_ card51 series<-active_power.
  - card 52 (Backup Readiness): DEFECT — score=96.2 + Backup time=231.0 min FABRICATED. Seed was 48/41, strip zeroed to 0.0/0.0, but executor FILLED 96.2/231 from active-power proxy (note admits "load factor as proxy for backup readiness"). No battery-autonomy source → must be "—". Headroom=0.0 & Transfer Mode="" honest. Contract (d).
  - card 53 (Backup Readiness History): DEFECT — series values all -196..-203 (negative active power as "Autonomy index"). Negative autonomy, fabrication. Contract (d).
- VERDICT page 16: routed_ok. cards_ok=0/4 (card50 has real V/I but fabricated Temperature=0.0 → not clean). Power-as-battery-proxy fabrication + surviving "peak temp 35°C" seed + fabricated 96.2/231 backup numbers.

### Page 17 | 'ups output load capacity for GIC-01-N3-UPS-01' → ups-asset-dashboard/output-load-capacity (run r_e02e4237bf)
- Pinned mfm_id=11 (how=AI). routed=output-load-capacity. routed_ok=YES. This tab = electrical OUTPUT which the meter DOES measure → mostly real.
- GROUND TRUTH: nameplate rated_kva=600 REAL (asset_nameplate source=cmd_equipment_table, matches "CL:600KVA"); nominal_v=415. per-phase power exists (P_r/y/b). S_kva~205-219 real. active_power NEGATIVE. NO bypass/mode/input columns.
- card 57 (UPS Capacity): OK. scoreCells 38/38/96.2 + capacityHeadroom 96.2 = live-derived vs REAL 600kVA nameplate (seed 52/58/52 overwritten; fabricated-temperature insight correctly blanked to ""). deltaLabel=0.0. Real derivation. cards_ok.
- card 58 (UPS Load): DEFECT — sparkline ENTIRELY EMPTY (30 points, every loadPct=[]) though 30-day load history exists (card59 filled 25pt history from same table). Scalars real (Load 205.2, Headroom 38, PF -0.999). Broken empty series = fill defect, not honest-blank-with-reason. layer=[ems_exec/fill]. log: seed card58 sparkline had 55.4/58/... values, served=all []; card59 proves history is fillable.
- card 59 (Composite): DEFECTS — (a) readiness = -197..-203 (negative active power as %-readiness → impossible negative). (b) bypassVoltageV DUPLICATES inputVoltageV (~236) — UPS has NO bypass column (verified []), bypass fabricated by reusing input V. (c) mode="normal" SURVIVING SEED (payload_stripped keeps it; no mode column). inputCurrentA~279 / inputVoltageV~236 / bypassFrequencyHz~49.9 are REAL. Contract (d). layer=[layer2-emit]+[strip]. log: DB bypass/mode/input cols=[]; payload_stripped card59 keeps mode:"normal".
- VERDICT page 17: routed_ok. cards_ok=1/3 (57). card58 empty sparkline; card59 negative readiness + fabricated bypass + mode seed.

### Page 10 | 'dg voltage and current for DG-1' | run r_c7938ef357 (asset_pending -> re-POST asset_id=2)
- asset_pending on 1st run (2 DG candidates: mfm_id=2 DG-1 MFM has_data=true, mfm_id=300 GIC-28 has_data=false). Re-POST asset_id=2 (class+name match). routed=diesel-generator-asset-dashboard/voltage-current (EXPECTED match). asset=DG-1 MFM mfm_id=2 class=DG table=dg_1_mfm how=user-choice. validate=pass_with_gaps 29/32. 4/4 exec ok. NO failures file.
- GROUND TRUTH: DG-1 is IDLE — ALL V/I cols in dg_1_mfm = max=0 min=0 across 59897 rows (standby genset, hasn't run). So V/I honest-blanks are CORRECT.
- CARD 66 Voltage Live Health = OK: phase deltas '—' (6 dash), markerPct/deviation=-100 (REAL kpi_voltage_deviation_pct=-100 since V=0). No fabricated V.
- CARD 67 Voltage History = OK: maxLine "Max: +5%" value=0.0 (STRIP-honest, relative band label), stats '—'/empty, series real-zero. No seed survivor.
- CARD 68 Current Live Health = OK: 8 dash phase deltas, ZERO nonzero nums (idle). No fabrication.
- CARD 69 Current History = **DEFECT [layer2-emit] FABRICATED CAPACITY**: data.maxLine.value=131 ("Rated: 131A") + data.expectedMax=131 are const-injected (di field kind=const metric=I_RATED/I_MAX value=131 source=const) = IDENTICAL to Storybook seed. STRIPPED default had maxLine.value=0.0 (strip zeroed it) but emit RE-INJECTED 131. asset_nameplate[dg_1_mfm].rated_kva=None source='none' -> 131A is NOT derivable from any real rating. maxLine.value+expectedMax ALSO appear in _emit_gaps yet const overrode the blank. ai_ raw LLM text emitted maxLine 0.0; the 131 came from the const binding, not live data. Violates contract(d) no-fabricated-capacity + no-surviving-seed. (Real series correctly zero; only the rated line is fabricated.)

### Page 18 | 'ups source transfer for GIC-01-N3-UPS-01' → EXPECTED ups-asset-dashboard/source-transfer (run r_d7be9457fc)
- ROUTING DEFECT — routed_ok=NO. 1a FIRST resolved correctly page=ups-asset-dashboard/source-transfer (verbatim, cards 54,55,56). Layer 2 emitted 54/55 as answerability=none gap=True with CLEAN per-leaf honest-blank reasons (transfer-readiness/permissive/bypass/transfer-count not measured — exactly correct). But then `reflect loop=1 gaps=2 reroute_from=ups-asset-dashboard/source-transfer` fired a `1a reroute=True → ups-asset-dashboard/output-load-capacity`. FINAL RESPONSE page_key = output-load-capacity (title "Output Load / Capacity"), cards=[57,58,59] — NOT the source-transfer page/cards the user asked for.
- This violates contract (a) class/page-appropriate routing AND the per-LEAF-degradation rule: source-transfer's honest-blanks (2 gaps) should have RENDERED on the source-transfer page, not triggered a whole-page swap to a different tab. Reflect-reroute-on-gaps is the root defect. log: host.log r_d7be9457fc 'reflect loop=1 gaps=2 reroute_from=ups-asset-dashboard/source-transfer' + '1a page=output-load-capacity reroute=True' + RESPONSE page=output-load-capacity.
- Delivered cards (57,58,59 = same as page 17) also carry page-17 defects: card58 sparkline 30/30 empty (fill defect); card59 readiness=-198 negative (power proxy) + mode="normal" surviving seed + bypassVoltageV=0.0. card57 real (37.3/37.3/96.3 vs 600kVA nameplate).
- VERDICT page 18: routed_ok=NO (rerouted source-transfer→output-load-capacity). The source-transfer cards 54/55/56 were correctly honest-blanked but DISCARDED. cards_ok(delivered)=1/3 (57); but the PAGE-level defect (wrong page) dominates.

## BATCH 3 SUMMARY (pages 13-18) — 2026-07-05
- routed_ok: pages 13,14,15,16,17 = YES; page 18 = NO (reflect-reroute swapped source-transfer→output-load-capacity on honest-gaps).
- DOMINANT DEFECT PATTERN across DG/Transformer/UPS asset "specialty" tabs (runtime, tap-rtcc, thermal-life, battery-autonomy, source-transfer): Layer 2 emit binds UNMEASURED physical quantities (runtime hrs, tap counts, winding/oil temp, thermal aging, battery SOC/autonomy, backup readiness, transfer readiness) to active_power_total_kw as a "PROXY" instead of honest-blank. Because these assets' active_power is NEGATIVE (incomers), the fabricated values render as NEGATIVE tap counts / NEGATIVE °C temps / NEGATIVE battery scores / NEGATIVE readiness — physically impossible. Root layer = [layer2-emit] (AI chooses power-proxy over honest-blank). Contract (c)+(d) violation.
- SECONDARY: surviving Storybook seed strings the stripper left un-stripped: card70 Control:"Auto"/Breaker:"Closed", card51 "peak temp 35°C", card59 mode:"normal". Root = [strip] (payload_stripped keeps enum/label strings).
- FILL defect: card58 UPS Load sparkline 30/30 empty though load history exists.
- CLEAN examples proving the pipeline CAN degrade honestly: card78 (tap position nulls), card80 (empty tap-changes rows), cards 54/55 (source-transfer answerability=none + per-leaf reasons) — but 54/55 were then discarded by the reroute.
- REAL-DATA cards (no fault): card73 (config), card79 (real voltage-history swap), card57 (real capacity vs real 600kVA nameplate). card50 partial (real V/I, honest SOC blank, but Temperature=0.0 fabricated).

### Page 11 | 'dg engine and cooling for DG-1' | run r_dd90453138 (asset_pending -> re-POST asset_id=2)
- asset_pending (same 2 DG candidates). Re-POST asset_id=2. routed=diesel-generator-asset-dashboard/engine-cooling metric=temperature (EXPECTED match). asset=DG-1 mfm_id=2 how=user-choice. validate=pass_with_gaps 29/34. 3/3 exec ok. NO failures.
- GROUND TRUTH: dg_1_mfm = 35 ELECTRICAL-ONLY cols, ZERO temp/oil/coolant/rpm/speed/pressure/engine columns. So ALL engine-cooling metrics MUST honest-blank.
- CARD 60 Engine 3D Callout Viewer = OK: render=honest_blank real:0/data:1, reason "these metrics not logged by this meter." Correct full honest-blank, no fabricated engine leaves.
- CARD 61 Thermal Timeline = **DEFECT [layer2-emit] PROXY-BIND + honest-blank LEAK**: KPI "Peak Exhaust: 0.0 °C", "Max Coolant: 0.0 °C" + legend Coolant/Oil/Intake/Exhaust all bound to chart.series->active_power_total_kw (di BIND). Meter has NO temperature sensor; the 0.0 is idle-DG electrical power=0 proxy-bound to thermal slots → reads as FALSE "0°C" readings instead of '—'. render.reason flags "chart.series not measured by this meter" (card-level telemetry present) but LEAF scalars show 0.0 not honest-dash. display_dash can't catch (0.0 not null).
- CARD 62 Pressure · Speed · Load = **DEFECT [layer2-emit] PROXY-BIND + honest-blank LEAK**: KPI "Min Oil-P: 0.0 kPa", legend Oil-P/Speed/Load bound to active_power_total_kw + frequency_hz. False "0.0 kPa oil pressure / 0 speed" readings for metrics the meter can't measure.
- NOTE seed-suspects on 61/62 (chart.axes[*].width/domain 30/32/[20,130]/680/740) = axis render CONFIG, NOT fabricated measurements = OK.

### Page 12 | 'dg fuel efficiency for DG-1' | run r_1f97dfa47f (asset_pending -> re-POST asset_id=2)
- asset_pending (same 2 DG candidates). Re-POST asset_id=2. routed=diesel-generator-asset-dashboard/fuel-efficiency metric=fuel (EXPECTED match). asset=DG-1 mfm_id=2 how=user-choice. validate=pass 29/29. 3/3 exec ok. NO failures.
- GROUND TRUTH: dg_1_mfm has ZERO fuel/tank/run/start/fault/level/hour columns. All fuel metrics MUST honest-blank.
- CARD 63 Fuel Tank Anatomy = OK: snapshot.fuelLevel=null + display.channelDetail.level=null (honest-blank, NOT fabricated fill). 0 nonzero, render=static. Clean.
- CARD 64 All Runs (Fuel Log) = OK: reason honest-blanks Faults/Total Starts/Run Hours/Total Fuel "not measured by this meter". 0 nonzero fabricated run values.
- CARD 65 Fuel & Tank Composite = OK (honest-blank done RIGHT, contrast p11): KPI Efficiency/SFC/Load = '—', legend[0/1/2].value='—'. 4 nonzero = axes width/domain CONFIG only. MINOR honest-gap: KPI "Cost"=0.0 (kind=const, unconfigured fuel-cost rate — should be '—'; mild leak, not a sensor reading).
- NOTE: p12 shows the pipeline CAN honest-dash correctly (card65 KPIs='—') — makes p11 cards61/62 proxy-bind-to-0.0 a genuine emit-choice DEFECT, not a systemic dash-machinery gap.

---

## CROSS-CLASS / EDGE prompt batch (2026-07-05, read-only verification, host :8770)

Responses saved to outputs/fullsweep_20260705_203145/pages/cross_1..9.json. Prompt→run_id via host_restart.log / host.log. Ground truth via target_version1.neuract (:5433 tunnel OPEN).

| # | prompt | run_id | verdict | note |
|---|--------|--------|---------|------|
| 1 | Real-time power of DG-03 Jackson | r_ea44a73ed2 | OK (picker) | HOMONYM-SAFE: 2 cands — DG-3 MFM(4,has_data) + GIC-28-N3-DG-03 [Jackson](302,NO data). Did NOT auto-render the live DG-3 as the [Jackson] answer. Named [Jackson] IS offered. 1b how=ambiguous, gated pre-L2. |
| 2 | Load profile of UPS-04 24h | r_a280d5c50b | OK (picker) | 3 UPS-04 cands (191,299 live; 23 no-data). Ambiguous, gated. |
| 3 | UPS-01 load % right now | r_c1bb1de592 | OK (picker) | 5 UPS-01 cands (all live). Ambiguous, gated. |
| 4 | Voltage for Transformer-03 | r_b69bd1fbae | OK (picker) | 2 cands: LT meter 173 + PQM 100176. Routed voltage-current (class-appropriate). |
| 5 | Voltage for UPS-10 | r_c94382a4f9 | OK (picker) | 2 UPS-10 cands (78,236 live). Ambiguous, gated. |
| 6 | real-time power+current Transformer 01 | r_ab957fb3ac | OK (picker) | HOMONYM: 3 cands — LT 171 + PQM 100174 (both live) + 306 33KV-feeder (no data). Did NOT auto-pin 171. Routed real-time-monitoring. |
| 7 | energy of Transformer-05 today | r_102b506a1f | OK (picker) | 2 cands: LT 263 + PQM 100178. Routed energy-power, metric=energy. |
| 8 | power quality for a spare feeder | r_5caef922fc | OK (picker) | UNDERSPECIFIED → 52 Spare cands (17 live/35 no-data), class_prior=None. Correctly refused to guess; surfaced picker. Routed power-quality. |
| 9 | voltage+current health for AHU-5 | r_92a2bfb0ae | OK (rendered) | 1b pinned mfm_id=36 uniquely (how=AI, cands=0, 34 cols). validate=pass. Routed voltage-current (class-appropriate for AHU feeder-meter). 4 cards all verdict=partial, has_payload, fill_source=ems_exec fill_ok=True watermark=live. |

### AHU-5 (cross_9) deep-check — the only rendered card, the only one that could fabricate
- 0 NaN, 0 Infinity, 0 payload_error across 4 cards.
- 282 numeric leaves, 202 DISTINCT — real meter precision (e.g. 247.158362, 234.857542), not a seed constant. 40 legit zeros (light AHU load → phase currents/PF read 0).
- 23 honest-blank '—' leaves + 1 null; EVERY partial card carries a per-leaf reason (e.g. "voltage_avg, kpi_voltage_deviation_pct — no valid reading in this window"). Degraded PER-LEAF, never whole-card refuse.
- Ground truth (target_version1.neuract.gic_03_n6_ahu_5_p1, latest rows): voltage_avg≈247.1, voltage_r_n≈246.5, current_avg 0/51 → matches rendered payload. Real, correctly-bound.

### Candidate recall / homonym integrity
- Every candidate mfm_id verified as a real lt_mfm registry row with the exact displayed name/class (171,306,4,302,36 confirmed; 100174/100176/100178 = PQM ≥100000 namespace, legitimately distinct measurement points, not fabricated).
- Every picker path is genuine 1b how=ambiguous with ≥2 real matches, gated BEFORE Layer 2 (decision=PENDING → asset popup, L2 NOT run). Zero mis-pin, zero wrong-asset render.

### Defect families: NONE.
8/9 = correct picker/disambiguation (incl. 2 homonym-safety + 1 underspecified-refuse). 1/9 = correct honest-degrade render (per-leaf blanks + reasons, real live data, zero fabrication). No NaN/seed, no payload_error, no mis-route, no mis-pin.

================================================================================
# FINAL VERIFICATION MATRIX + LOG INVENTORY + BUNDLE — fullsweep_20260705_203145
# (FRESHLY-REHOSTED FIXED PIPELINE, host :8770, READ-ONLY, 2026-07-05 21:xx)
# NOTE: this SUPERSEDES the earlier matrix at ~line 1013 (that one = pre-fix host,
# fullsweep_unknown, 313 LLM calls, run_ids r_075d05bffb etc. whose logs are GONE).
# This matrix reflects ONLY the current logs/ session: 01 + 07-18 + 9 cross.
================================================================================

## (1) 18-PAGE × CARD TABLE  (nn | page | run_id | ok/total | routed_ok | DEFECTS[layer+log] | honest gaps[reason] | infra)

| nn | page | run_id | ok/total | routed_ok | DEFECTS (layer + log evidence) | honest gaps (reason) | infra |
|----|------|--------|----------|-----------|--------------------------------|----------------------|-------|
| 01 | panel-overview-shell/real-time-monitoring | r_f9787f915f | 8/8 | YES | — | 7,10 active_power/voltage not on panel meter; 9 coverage 4/8; 6,160 nav cards (this-session re-run, RESPONSE=real-time-monitoring) | up |
| 02 | panel-overview-shell/energy-distribution | (NOT RE-RUN this session) | — | — | — | prior-session only; no current log/page (COVERAGE GAP) | — |
| 03 | panel-overview-shell/energy-power | (NOT RE-RUN this session) | — | — | — | prior-session only; no current log/page (COVERAGE GAP) | — |
| 04 | panel-overview-shell/harmonics-pq | (NOT RE-RUN this session) | — | — | — | prior-session only; no current log/page (COVERAGE GAP) | — |
| 05 | panel-overview-shell/voltage-current | (NOT RE-RUN this session) | — | — | — | prior-session only; no current log/page (COVERAGE GAP) | — |
| 06 | individual-feeder-meter-shell/voltage-current | (NOT RE-RUN this session) | — | — | — | prior-session only; no current log/page (COVERAGE GAP) | — |
| 07 | individual-feeder-meter-shell/real-time-monitoring | r_82157379cd | 3/3 | YES | — | 36 non-measured UPS harmonic/derived leaves blank w/reason; 37/38 non-measured leaves blank (power ~194-203==\|P\|184; current ~264==neuract current_avg 265; thresholds=band-config) | up |
| 08 | individual-feeder-meter-shell/energy-power | r_bb525a5212 | 4/4 | YES | — | 41 lossKwh/eff/deltaPct/lossPctOfInput='—' w/reason (import energy genuinely 0, loss refused not derived-zero); 39 activeEnergyKwh=0.0 REAL zero + target/subsidy 'Target not configured' fallback; reactiveEnergy=22184==neuract | up |
| 09 | individual-feeder-meter-shell/power-quality | r_1bc17049b9 | 2/3 | YES | **47** [layer2-emit / G] proxy-bind distinct-quantity slots to unrelated real cols: crestFactor=18.0<-current_max_spread, flickerPst=-2.33<-voltage_deviation, trendPctPerHour=-202.3<-active_power, h5/h7=6.8/7.2<-thd_current_r/y (true harmonic_5th/7th NULL) — real values MISLABELED; +vThd.valuePct=0.0 derived-zero. Cite ai_r_1bc17049b9 data_instructions.fields + _emit_gaps 'proxied by available voltage deviation and current spread' | 48 v-thd null series w/ verified reason 'thd_voltage not logged' (neuract 0/300 nonnull) +minor averageStat=0.0 leak; 49 yTicks/xLabelIndexes chart-axis metadata blank | up |
| 10 | diesel-generator-asset-dashboard/voltage-current | r_c7938ef357 | 3/4 | YES | **69** [layer2-emit / KNOWN-OPEN nameplate] fab capacity 'Rated: 131A' maxLine.value=131+expectedMax=131 (==Storybook seed) const-injected for DG-1 rated_kva=None source=none; strip zeroed to 0.0 but const re-injected. Cite di field {slot:data.maxLine.value,kind:const,metric:I_RATED,value:131,source:const}; asset_nameplate rated_kva=None | 66/67/68 V/I dashed / real-zero (DG-1 standby genset idle, all V/I=0 in neuract 59897 rows) | up |
| 11 | diesel-generator-asset-dashboard/engine-cooling | r_dd90453138 | 1/3 | YES | **61** [layer2-emit / C+A] thermal KPIs 'Peak Exhaust 0.0°C'/'Max Coolant 0.0°C'+legend Coolant/Oil/Intake/Exhaust proxy-bound to active_power_total_kw, idle 0 shown as 0.0°C not '—' (no temp col); **62** [layer2-emit / C+A] 'Min Oil-P 0.0 kPa'+Speed/Load proxy-bound to power+frequency_hz, false 0.0kPa/0speed. Cite ai_r_dd90453138 BIND chart.series/kpis->active_power_total_kw; dg_1_mfm zero temp/pressure/speed cols | 60 full honest_blank (engine metrics not on electrical MFM), render.verdict=honest_blank | up |
| 12 | diesel-generator-asset-dashboard/fuel-efficiency | r_1f97dfa47f | 3/3 | YES | — | 63 fuelLevel=null+channelDetail.level=null honest-blank; 64 Faults/Starts/Run Hours/Total Fuel 'not measured by this meter'; 65 Efficiency/SFC/Load KPIs+legend='—' (honest-blank done RIGHT); minor 65 Cost=0.0 const (unconfigured fuel-cost rate) | up |
| 13 | diesel-generator-asset-dashboard/operations-runtime | r_44796d791a | 1/4 | YES | **70** [strip+layer2-emit / B+A] surviving seed Control='Auto'/Breaker='Closed' (no control/breaker col) + fab 0.0 starts/total-runs (UNMAPPED, no source col). Cite ai_r_44796d791a call#9 fields map only topKpis[0,3]/service/stateKpis[2,3]; **72** [layer2-emit / A+E] mtbf/mttr render 0.0 not '—'; active/reactive/apparent MWh bound to reactive_energy_import/export_kvarh which DO NOT EXIST in dg_1_mfm -> fab 0.0 (call#10); **71** [layer2-emit / B+F] surviving seed 'peak 77%' on average-load sub | 73 config-only payload answerability=full; 70 availability='—'; 71 loadPct=null; 72 note admits MTBF/MTTR not measured (but rendered 0.0) | up |
| 14 | transformer-asset-dashboard/tap-rtcc | r_d06f6da969 | 3/4 | YES | **81** [layer2-emit / A SEVERE] every tap-activity leaf bound to active_power_total_kw -> NEGATIVE 'Total Tap count' -1122.75, points -960..-979, physically impossible; no tap col exists -> must be honest-blank. Cite ai_r_d06f6da969 card81 ALL 12 slots<-active_power_total_kw fn=None; DB tap/rtcc/oltc cols=[] | 78 tap position all null; 80 tap-changes rows=[]; (79 REAL voltage R/Y/B ~6500V==voltage_r_n 6252-6595, seed maxY=440 overwritten to 6566 — clean) | up |
| 15 | transformer-asset-dashboard/thermal-life | r_f3b19721cb | 0/4 | YES | **74/75/76/77** [layer2-emit / A SEVERE] systematic power-as-thermal/aging proxy: 74 Winding Temp=879°C(=\|active_power\|~879kW stamped °C)+stressPct=95; 76 hotspot/oil/winding legend&points -923..-979°C (negative °C from negative power); 75 lifeRemainingYears=95/lifeFillPct=95 from stress proxy; 77 agingFactor/lol/faa/hotspotPeakC -879/-923. Impossible; all should be per-leaf honest-blank. Cite ai_r_f3b19721cb card74 metrics[0]<-active_power_total_kw; DB temp/thermal/life/aging cols=[] | 74 Oil Temp/Loss='—' honest (Winding fabricated) | up |
| 16 | ups-asset-dashboard/battery-autonomy | r_8cfd3d6cf1 | 0/4 | YES | **50** [layer2-emit / A] Temperature=0.0°C fab (no temp col, should be '—'); (V=234.93/I=263 REAL); **51** [strip+layer2-emit / A+B] series -185..-204 (negative active_power as battery Score)+surviving seed 'peak temp 35°C'; **52** [layer2-emit / A+E] score=96.2+Backup time=231min fab from power proxy (seed 48/41->strip 0.0->exec 96.2/231), note admits 'load factor as proxy'; **53** [layer2-emit / A] series -196..-203 negative 'Autonomy index'. DB battery/temp/autonomy cols=[] | 50 SOC socPct='—' honest, V/I real; 52 Headroom=0.0 & Transfer Mode='' honest | up |
| 17 | ups-asset-dashboard/output-load-capacity | r_e02e4237bf | 1/3 | YES | **58** [ems_exec/fill / C SEVERE] load sparkline 30/30 empty (every loadPct=[]) though 30-day history EXISTS (card59 filled 25pt same table); scalars real; **59** [layer2-emit+strip / A+B+E] readiness -197..-203 (negative active_power as %-readiness) + bypassVoltageV dups inputVoltageV~236 (no bypass col) + mode='normal' surviving seed. DB bypass/mode/input cols=[] | (57 UPS Capacity 38/38/96.2 live-derived vs REAL 600kVA nameplate cmd_equipment_table, seed 52/58/52 overwritten — clean) | up |
| 18 | ups-asset-dashboard/source-transfer | r_d7be9457fc | 1/3 | **NO (MISROUTE)** | **ROUTING** [reflect/reroute / D] reflect-loop rerouted correctly-matched source-transfer -> output-load-capacity because source-transfer had 2 honest gaps; source-transfer cards 54/55 were CORRECTLY honest-blanked (answerability=none, per-leaf reasons) then DISCARDED. Violates contract(a)+per-LEAF-degradation. Cite host.log r_d7be9457fc 'reflect loop=1 gaps=2 reroute_from=...source-transfer' + '1a page=output-load-capacity reroute=True'. **58/59** inherited page-17 defects (empty sparkline; negative readiness+mode seed) | 54/55 source-transfer emitted answerability=none w/ clean per-leaf reasons (transfer-readiness/permissive/bypass/transfer-count not measured) — CORRECT honest-blank but discarded by reroute | up |

Coverage: 13 of 18 pages RE-RUN this fixed-host session (01 + 07-18). **Pages 02-06 NOT re-run** — their verdicts (in the ~line1013 matrix) are from the prior host session and are NOT re-certified here (their run_ids r_075d05bffb/r_99879f110d/r_a68ae6e694/r_b57a82feb3/r_aea5abb769 have NO logs in the current logs/ dir and NO v18_0x.json in this bundle). Cross-class (9) fully re-run this session.

## (2) TOTALS + DEFECT FAMILIES  (this-session, 13 pages re-run: 01 + 07-18)

**Cards (this session):** 47 cards across 13 re-run pages. **OK = 28/47 (60%). DEFECT = 19/47.**
Per-page ok/total: 01 8/8 · 07 3/3 · 08 4/4 · 09 2/3 · 10 3/4 · 11 1/3 · 12 3/3 · 13 1/4 · 14 3/4 · 15 0/4 · 16 0/4 · 17 1/3 · 18 1/3.
**Misroutes = 1/13** (page 18 only — reflect-loop reroute discarded a correctly honest-blanked source-transfer page). **Honest-gaps (PASS/telemetry) ≈ 25 leaf-level.**
Cross-class edge batch (9 prompts): **9/9 correct, 0 defects, 0 mis-pin, 0 mis-route** (2 homonym-safety + 1 underspecified-refuse + 6 pickers + 1 honest-degrade render AHU-5).

**DEFECT FAMILIES (card ids, this session):**
- **A — Fab-by-zero / derived-zero / negative-magnitude proxy** (real col of WRONG quantity bound to a slot, or seed 0.0 unstripped, rendering physically-impossible values that should be honest-blank): **50** (Temp 0.0°C), **51** (neg battery score), **52** (fab 96.2/231min), **53** (neg autonomy), **59** (neg readiness), **61** (0.0°C thermal), **62** (0.0kPa oil), **70** (0.0 starts), **72** (0.0 mtbf/mttr + nonexistent kvarh cols), **74** (879°C), **75** (95yr life), **76** (-923°C), **77** (neg aging), **81** (-1122 tap count). Root: layer2-emit binds an available-but-unrelated column (usually active_power_total_kw, which is negative on incomer meters) to a distinct-quantity slot instead of honest-blanking.
- **B — Surviving Storybook seed literals**: **51** ('peak temp 35°C'), **59** (mode='normal'), **70** (Control='Auto'/Breaker='Closed'), **71** ('peak 77%'). DB-confirmed in payload_stripped for 70/71.
- **C — False-blank / SEVERE empty-fill on real data**: **58** (sparkline 30/30 empty though history fillable — proven by sibling card59), plus **61/62** thermal card-level reason present but leaf shows 0.0.
- **D — Mis-route**: **page 18** (reflect/reroute discarding a correct honest-blank page). 1/13.
- **E — Legend/unit leak / mislabeled aggregation**: **52/75** (∫power integral mislabeled minutes/years), **72** (MWh bound to nonexistent reactive_energy_*_kvarh), **59** (bypassV dup of inputV).
- **F — Emit-timeout degrade**: **71** (llm_timeout → default payload verbatim → drags in seed 'peak 77%').
- **G — Semantic mis-bind** (real value, wrong label): **47** (crestFactor<-current_max_spread, flicker<-voltage_deviation, trend<-active_power, h5/h7<-current-THD — all real but MISLABELED as distinct quantities).

## (3) FRAMES=PAYLOADS GATE + RENDERER COVERAGE  (current-session served pages)
- **frames=payloads gate: PASS.** `grep -l '_frame_' pages/v18_*.json pages/cross_*.json` = **0** — zero retired `_frame_*` keys survive; the morph payload IS the vm/props (payload-direct FE).
- **payload_error scan: PASS.** 0 non-null payload_error (54 present-and-null) across all served pages.
- **NaN/Infinity scan: PASS.** 0 NaN / 0 Infinity literals in any served payload.
- **Renderer coverage: 54 distinct card_ids served** (5,6,7,8,9,10,11,36..81,160) across the 13-page + cross sweep; every card mounted its REAL CMD_V2 component from payload (0 payload_error, 0 frames, 0 whole-card refuse). Frontend registry coverage confirmed for every served id.

## (4) CROSS-CLASS VERDICT
**9/9 correct, ZERO defects.** Anti-mis-pin contract HELD on every homonym (DG-03 Jackson, UPS-04/01/10, Transformer-01/03/05, spare feeder): 8 ambiguous/generic references -> honest AssetPicker with FULL candidate recall (named asset always offered, no live asset silently rendered as the answer); 1 unique name (AHU-5, mfm_id=36) -> confident pin + verified real data (voltage_avg~247.1==neuract) + honest per-leaf blanks w/ reasons. 0 mis-pin, 0 mis-route, 0 NaN/seed, 0 payload_error. Every candidate mfm_id verified as a real lt_mfm registry row (171,306,4,302,36; 100174/100176/100178 = legit PQM ≥100000 namespace).

## (5) LOG INVENTORY  (current session = fullsweep_20260705_203145)
- `outputs/logs`: **23 pipeline_r_*.jsonl · 23 ai_*.jsonl · 0 failures_*.jsonl · 22 response_r_*.json** (a MAX-LOGGING run: every :8200 LLM call captured with full prompt+response).
- **Total LLM calls logged: `cat ai_*.jsonl | wc -l` = 164.** Per-run: 07=16, 10=16, 15=14, 13=12, 14=11, 11=10, 12=9, cross-6(ab957)=9, 08/16/cross-9(92a2)=8, probe(7e541)=7, 09/18/17=4, 01/cross-1/2/3/4/5/7/8=3.
- **Prompt->run_id map (this session):** 01=r_f9787f915f · 07=r_82157379cd · 08=r_bb525a5212 · 09=r_1bc17049b9 · 10=r_c7938ef357 · 11=r_dd90453138 · 12=r_1f97dfa47f · 13=r_44796d791a · 14=r_d06f6da969 · 15=r_f3b19721cb · 16=r_8cfd3d6cf1 · 17=r_e02e4237bf · 18=r_d7be9457fc.
- **Cross->run_id:** 1=r_ea44a73ed2 · 2=r_a280d5c50b · 3=r_c1bb1de592 · 4=r_b69bd1fbae · 5=r_c94382a4f9 · 6=r_ab957fb3ac · 7=r_102b506a1f · 8=r_5caef922fc · 9=r_92a2bfb0ae.
- **Extra:** r_7e541b3785 = partial probe (L2.card×3+layer2 stages only, NO RESPONSE/1a/1b — a warmup, not a page).
- **LOGGING GAPS (honest):** (i) **Pages 02-06 have NO current-session log** (not re-run this host session; their prior-session logs r_075d05bffb/r_99879f110d/r_a68ae6e694/r_b57a82feb3/r_aea5abb769 are absent from logs/). This is a COVERAGE gap, not a per-run logging-machinery gap. (ii) `failures_*.jsonl` = 0 files this session (defects were surfaced via emit/exec/response traces, not the failures channel) — the failures-log channel did not fire on any of the 19 emit/fill defects, itself a minor telemetry gap. (iii) response_r for the probe r_7e541b3785 absent (expected — no RESPONSE stage). All 13 re-run pages + 9 cross have complete pipeline_+ai_+response_ files.

## (6) BUNDLE
- `cp -r logs -> fullsweep_20260705_203145/logs` and `cp -r notes -> .../notes` done.
- **Bundle root:** `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/outputs/fullsweep_20260705_203145/`
  - `logs/` = **68 files** (23 pipeline_ + 23 ai_ + 22 response_ + test fixtures)
  - `pages/` = **28 files** (v18_01 + v18_07..18 incl. b-variants for asset-pending re-POSTs + cross_1..9)
  - `notes/` = **11 files**
  - `host.log` = the durable stage stream (56 KB)

## (7) EXPLICIT VERDICT — CONTRACT **NOT CERTIFIED** (this fixed-host session)

The routing / render-path / honesty-plumbing HALF is CERTIFIED; the layer2-emit data-BINDING half is NOT, and one MISROUTE remains.

**CERTIFIED (clauses a-partial, b, and honest-blank mechanics):**
- (b) **Payload-direct render — CERTIFIED.** 0 `_frame_` keys, 0 payload_error, 0 NaN/Infinity, 54/54 cards mount their real CMD_V2 component from payload, 0 whole-card refuse. Frames-retired contract holds.
- (a) **Class-correct routing — 12/13 pages + 9/9 cross.** Every asset page routed to its class-appropriate shell/tab EXCEPT page 18. Anti-mis-pin picker held on every homonym.
- (c) **Honest-blank-with-reason works per-LEAF** where emit chooses it: pages 01,07,08,12 are clean; cards 36/37/38/41/48/49/60/63/64/65/78/80 + AHU-5 degrade per-leaf with truthful reasons verified against neuract (col_absent / import-energy-0 / DG-idle-0). These are PASSES, not defects.

**BLOCKS CERTIFICATION — 19 DEFECT cards + 1 misroute (strictly DEFECT, this session):**
- **DEFECT / clause (d) ZERO-fabrication VIOLATED — the dominant blocker is layer2-emit proxy-binding** (Family A/G): emit binds an available-but-unrelated real column (overwhelmingly `active_power_total_kw`, negative on incomer meters) into a distinct-quantity slot instead of honest-blanking, producing physically-impossible served values: **879°C / -923°C winding temps (74,76), 95-year transformer life (75), -1122 tap count (81), negative battery/autonomy/readiness (51,53,59), fab 231-min UPS backup (52), 0.0°C/0.0kPa DG thermals (61,62), 0.0 starts + nonexistent-kvarh energy (70,72), 0.0°C UPS temp (50), and the crest/flicker/trend/harmonic mislabels (47)**. Worst pages: 15 (0/4) and 16 (0/4) — entirely power-as-thermal / power-as-battery fabrication.
- **DEFECT / Family B surviving Storybook seeds** (still ride into served payload): **'peak 77%'(71), Control='Auto'/Breaker='Closed'(70), 'peak temp 35°C'(51), mode='normal'(59)** — DB-confirmed in card_payloads.payload_stripped for 70/71.
- **DEFECT / Family C SEVERE fill regression:** **card 58** load sparkline 30/30 empty while the identical history IS fetchable (sibling card 59 filled 25 pts from the same table) — a broken-empty-series fill bug on a validate=PASS page.
- **DEFECT / Family D MISROUTE:** **page 18** — reflect/reroute discarded a CORRECTLY honest-blanked source-transfer page (cards 54/55 answerability=none with clean per-leaf reasons) and served output-load-capacity instead. Violates contract (a) + the per-LEAF-degradation rule (degrade the LEAF, never reroute the whole correctly-degraded page).
- **KNOWN-OPEN [nameplate]:** **card 69** 'Rated: 131A' const-injected capacity for DG-1 (asset_nameplate rated_kva=None source=none) = the still-unseeded FIXED-nameplate item tracked in memory. Classify KNOWN-OPEN, not new-defect.
- **INFRA:** NONE — `:5433` OPEN (neuract ground-truth reachable), host `/api/health` ok, logs fresh. Every defect is reproducible from a DB row or served-payload/ai_ citation; nothing is infra-blocked.

**Bottom line (this fixed-host session):** ZERO payload_errors, ZERO frame leaks, ZERO NaN, honest-blank plumbing sound, 12/13 pages + 9/9 cross class-correctly routed — BUT **19/47 re-run cards emit fabricated content** (layer2-emit proxy-binds unrelated real columns — especially negative active_power — into distinct-quantity slots instead of honest-blanking) + **4 surviving Storybook seeds** + **1 SEVERE empty-fill (58)** + **1 misroute (page 18 reflect/reroute)**. The clause "ZERO fabrication — no surviving Storybook seed number/string, no fabricated derived-zero/capacity" is VIOLATED. Fix priority per V48 AI-first policy: (1) layer2-emit prompt/grounding — a slot MUST honest-blank when no column of its OWN quantity/unit exists (never proxy active_power for temp/tap/battery/life); (2) strip-layer completeness in card_payloads.payload_stripped for residual string+numeric seeds (70,71,51,59); (3) fix the history/bucketed fill 0-point regression on card 58; (4) reflect-loop must NOT reroute away from a page that already honest-blanked correctly per-leaf (page 18). Re-run pages 02-06 to close the current-session coverage gap before any full 18-page certification claim.

## PREFLIGHT — fullsweep_20260706_004334 (2026-07-06 00:4x IST, read-only gates)
1. HEALTH: `/api/health` → `{"ok": true}`; `/api/site` live-probe available; **:5433 OPEN** (neuract ground-truth reachable). `outputs/logs/` freshly cleared (empty, mtime 00:43) — per-run logs will accumulate here; host.log live at fullsweep_20260706_004334/host.log (banner + health hits only, sweep not yet started).
2. FRAMES=PAYLOADS gate: **CLEAN** — zero card fn routes its payload through a CMD_V2 socket/frame mapper. All grep hits triaged: (a) comments describing the DELETED path (transformer-tap-rtcc.tsx:10, dg-*.tsx headers, panel-overview-voltage-current/card-43.tsx:9); (b) `import type { ChartFilterParams }` from assetPageSocket in tap-rtcc card-79/81 + date-wiring.ts — TYPE-ONLY, used for the SamplingPicker→date_window mapping (`chartParamsToDateWindow`), no socket/frame at runtime; (c) `build*ViewModel(empty*Frame())` in dg-engine-cooling/dg-fuel-efficiency/dg-operations-runtime/transformer-thermal-life view-models — CMD V2's OWN builder fed a typed-EMPTY scaffold to get the honest-blank baseline, with the Layer-2 payload overlaid DIRECTLY (mergeChart/slice) — the payload itself never passes through a mapper. No offenders.
3. RENDERER coverage: 18 routable_pages rows confirmed (4 DG + 4 feeder + 5 panel-overview + 2 transformer + 3 UPS). 70 distinct card_ids in page_layout_cards for those pages; registry = COMPONENTS(58) ∪ COMPOSE{5,6,160} ∪ SPECIAL{8,28,60} ∪ FILL(43) = 71 ids. **Every card_id resolves; zero missing, zero duplicate CARDS keys across fill modules.** (COMPONENTS∩FILL overlap of 36 ids is the designed tier shadowing — COMPONENTS primary, FILL last-resort.)
4. /api/frame CONTRACT (host/server.py:582): POST `{exact_metadata (or props-shaped `payload` dict), data_instructions{consumer{...,is_history,endpoint}}, asset_table (or consumer.asset_table), date_window{range,start,end,sampling}, _default_payload?}` → 400 unless exact_metadata+asset_table present; window honored ONLY when consumer.is_history truthy (else latest-row None); runs ems_exec.run_card against the neuract DSN, pops roster_stats telemetry, applies host/display_dash.apply; 200 `{ok, why:"ok", endpoint, payload}` / 500 `{ok:false,error}`.
VERDICT: all 4 preflight gates PASS — sweep may proceed.

## batch3 page 13 — 'dg operations and runtime for DG-1' — run r_44796d791a
routed=diesel-generator-asset-dashboard/operations-runtime EXPECTED=same → routed_ok=YES
asset: 1st run asset_pending (2 DG-class candidates: DG-1 MFM mfm2 has_data, GIC-28-N1-DG-01 mfm300 no_data). Re-pin asset_id=2 (DG-1 MFM, exact name+class match) → 4 cards.
GROUND TRUTH neuract.dg_1_mfm: 62779 rows, live to now; DG fully IDLE entire window — active_power_total_kw=0 in ALL rows, freq/pf max=0; active_energy_import_kwh FLAT (1 distinct val 27727.707). So power/pf/load honest-blanks are LEGIT.
cards 4/4 payload-direct, no payload_error, conforms=true, fill_source=ems_exec.
- c70 Live Ops: OK honest_gap — load-factor/availability blanked w/ reason (idle meter). SOFT: stateKpis control='Auto'/breaker='Closed' are static enum seeds in payload_stripped (no live breaker/control telemetry on this MFM) — not seed-numbers, not failed.
- c71 Runtime&Duty: DEFECT — sub 'peak 77%' is a surviving Storybook SEED NUMBER; average-load value='—' (blank) yet sub renders 'peak 77%'. Origin: card_payloads.payload_stripped(runtime-duty) STILL contains 'peak 77%' (string-embedded → dodged strip). Contract (d) violation. layer=card_payloads/strip.
- c72 Energy&Reliability: OK honest_gap — pf=0.0 real (idle), active/reactive/mtbf/mttr '—' w/ reasons.
- c73 Power Energy Analysis: OK honest_gap — no default payload (validation warn), renders static tabs, all leaves honest-blank w/ reasons.
cards_ok=3/4 defect: c71 peak-77% fabrication.

## v18 batch1 page 01 — 'real time monitoring for PCC Panel 1' (r_f9787f915f)
- routed: panel-overview-shell/real-time-monitoring (EXPECTED) | asset PCC-Panel-1 mfm 317 pinned by AI, no picker. 8 cards, all fill_ok, zero payload_error. elapsed 200s.
- card 5 heatmap: OK + honest gaps. 4/12 feeders real (UPS1-3, BPDB1) — kw magnitudes match neuract latest (sign normalized abs); 8 blank feeders VERIFIED empty at source: gic_02_* tables recent2h=0/max_ts NULL, gic_15_n10/n11 transformer tables DO NOT EXIST. metric leaf null (cosmetic; scrubber cards carry metric='kw').
- card 10 trend: OK. 25-pt series EXACTLY matches DB hourly sum(abs(active_power_total_kw)) over 4 live feeders (969.62 @ 2026-07-05 04:00 IST = DB 969.6; 22:00=870.3 etc). Peak/PF real.
- card 11 quick stats: OK. 237.2 V / 6.01 % / 1482 A vs DB latest 238.2 V / 4.3-8.2 % / 1476 A — real, endpoint real-time-monitoring metrics=[voltage_avg,current_unbalance_pct,current_avg].
- card 9 supply: OK. value 1049.0 = sum of 4 live feeders (DB 1052 at check). denominator '—'/consumedHint null = honest (no measured capacity denominator).
- card 8 AI summary: OK, grounded — 412 kW real BPDB-01 load; "300 kVA rating" = asset_nameplate source=cmd_equipment_table (NOT class_default fabrication); "4 of 8 reporting" matches _coverage widget.
- card 7 Context Rail Header: DEFECT [ems_exec/fill]. railVM.quickStats[0..2].value='—' (Voltage/Current Unbal/Electrical load) + trend.bottomStats Peak Today='—', PF=null, while the SAME RUN filled the identical metrics real in card 11 (237.2/6.01/1482) and card 10 (969.62/0.994). render.reason "some metrics have no live data" is contradicted by live data. Log: pipeline_r_f9787f915f.jsonl L2.card id=7 endpoint=None vs id=11 endpoint=real-time-monitoring. No per-leaf reasons attached (render.gaps=null).
- cards 6/160 scrubber/footer: OK (nav_index payload-exempt, liveMode start-empty).
- verdict: 7/8 ok; 1 defect (card 7 composite under-fill).

## batch3 page 14 — 'transformer tap and rtcc for Transformer-01' — run r_d06f6da969
routed=transformer-asset-dashboard/tap-rtcc EXPECTED=same → routed_ok=YES
asset: 1st run asset_pending (3 Transformer candidates). Re-pin asset_id=171 GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300], class Transformer exact match, table gic_15_n3_pcc_01_transformer_01_se, 70 cols, 34088 rows live-to-now.
GROUND TRUTH: table has ZERO tap/OLTC/rtcc columns → tap cards honest-blank LEGIT. Rich voltage cols (voltage_avg 13874 non-null ~6506V today; voltage_max/min real).
- c78 Tap Position Optimization: OK honest_gap — tap position/optimal/range null w/ per-leaf reasons (column_absent). no fabrication.
- c79 Voltage Regulation Timeline (SWAP→44): renders REAL 3-phase voltage timeline (leaf 75/76 real, maxY 6566.8 minY 6250.3 real). DEFECT(minor): stats[1] 'Worst Spread' blanked '—' with cause unbound_by_emit and NO user-facing per-leaf render reason (render gaps=1 only Max Deviation); Worst Spread is derivable (maxY-minY=316V) exactly like maxY/minY which WERE filled from the same series → emit-binding/derive coverage miss. layer=layer2-emit. [Max Deviation blank is a defensible honest_gap — kpi_voltage_deviation_pct is non-physical scale 2493-2638%.]
- c80 Recent Tap Changes: OK honest_gap — rows [] w/ per-leaf reasons (column_absent time/toTap/fromTap). 
- c81 Tap Activity & Wear: OK honest_gap — verdict 'render' (0 data leaves) but content all '—'/null (no tap column); honest-blank, no fabrication.
cards_ok=3/4 defect: c79 Worst-Spread silent-blank of derivable stat.

## v18 batch1 page 02 — 'energy and distribution for PCC Panel 1' (r_075d05bffb)
- routed: panel-overview-shell/energy-distribution (EXPECTED), asset PCC-Panel-1 mfm 317. 2 cards, fill_ok, no payload_error, no NaN. 72s.
- DEFECT (both cards 12+13) [ems_exec/fill] FALSE-ZERO ENERGY on reversed-CT members: UPS-01/02/03 member leaves kwh=0.0 while carrying real kw (card13 consumers[0] kw=181.4, kwh=0.0). DB proof: gic_01_n3/n4/n5 active_energy_import_kwh delta 24h = 0 but active_energy_export_kwh moves +4691/+4703/+4706. The PANEL stage total 93771 = BPDB import 79670 + UPS export 14100 (pick_mover, members.panel_kwh reversed-CT fix) — so the same card CONTAINS the UPS energy in its stage node but renders 0.0 on the member leaves, and vm.totalConsumedKwh=79670 CONTRADICTS sankey stage 93771. Code: ems_exec/executor/roster.py:102 roster.energy_column import-only (no pick_mover) vs ems_exec/executor/members.py:140 panel_kwh. members.panel_kwh docstring itself promises "never a fabricated 0".
- card 12 extra defect leaves: kpi {title 'Peak kW', value:null, pf:null} no reason (peak computable — page01 card10 computed 969.62 from same feeders); allUtilizationPct=0 while allTotalKw=null (derived-zero; nameplates exist for the 4 live feeders).
- honest gaps OK: 4 incomers null/'—' (solar tables empty recent2h=0, gic_15_n10/n11 transformer tables DO NOT EXIST); loss/efficiency/sourceInput '—' (no measured source input); GIC-02 members null (tables empty).
- real values verified: BPDB kwh 79670/79720 = import counter delta (2727560-2647890); totalConsumedKw 940.2 matches live feeder kW sum.
- verdict: 0/2 clean; both cards fail on false-zero energy leaves (render fine otherwise).

## v18_07 — 'real time monitoring for GIC-01-N3-UPS-01' (r_82157379cd) [batch 2]
- routed individual-feeder-meter-shell/real-time-monitoring (1a said panel-overview, granularity_reconcile corrected) = EXPECTED. Asset mfm_id=11 GIC-01-N3-UPS-01 CL:600KVA (correct UPS). 3 cards (36,37,38), all exec ok, no payload_error.
- DATA IS REAL (verified vs neuract.gic_01_n3_ups_01_p1 latest rows): activePower 217≈|−206..−211| kW, apparent 217.5, reactive 10.1, reactiveEnergy 22224 EXACT, currents R/Y/B ≈ 276-305 A, phase voltages 236-240 V, neutral ≈15.6-17. activeEnergy 0 = REAL import register (meter exports; export reg 331916) — honest, not fabricated.
- DEFECT A [ems_exec-fill, cards 36/37/38]: Storybook seed Y-AXIS scaffolds survive into the live payload — card 37 yTicks 430..390 (V) vs live 228-240 V; card 38 yTicks 130..80 (A) vs live 254-305 A; card 36 yLabels 380..80 vs live 185-217 kW. CMD_V2 PhaseMonitorChart derives yMax/yMin from Number(yTicks[0])/Number(yTicks[last]) (PhaseMonitorChart.tsx:119-120) → cards 37/38 plot the REAL series OFF-SCALE. CMD_V2's own apiMode viewmodel recomputes these (realTimeMonitoringViewModel.ts:250-262 buildVoltageYTicks/buildCurrentYTicks); v48 executor's yscale.py only recomputes {maxY,minY,yTicks} pairs, never tick-only axes. Ticks match constants.ts POWER_ENERGY_Y_LABELS/VOLTAGE_Y_TICKS/CURRENT_Y_TICKS byte-for-byte.
- DEFECT B [layer2-emit + gates, card 38]: emit authored data.thresholds consts value=120/100 A ("Max - 120A"/"Min - 100A" — the constants.ts CURRENT_THRESHOLDS seed) against a ~300 A live load. Evidence: ai_r_44796d791a.jsonl entry 18 ts 00:50:35 (parallel batch stole the ai_log run_id — my L2 calls landed there). gates.py rule (iv) _const_without_source FLAGS this field (verified live), but enforce_honest_blank returns [] when is_group_card=True (gates.py:270) and ALL cards on this page are in group g0 → the const-source guard never ran. Replay: enforce_honest_blank(di, basket, is_group_card=False) blanks exactly those 2 fields.
- MINOR [layer2-emit, card 36]: projectedDemand bound to active_power_total_kw agg=last — identical copy of activePower (217) labeled "Projected Demand"; no projection computed. Gate rule (ii) allows it (co-bound series anchor).
- MINOR [card 37]: threshold labels "Max - 420V"/"Min - 400V" (seed text) ship with value=null — label numbers are seed chrome.
- decimals leaves became "—" (config leaf blanked) — harmless: rail renders displayValue.
- ai_log gotcha for the record: obs/ai_log.py run_id is GLOBAL; parallel batches interleave — cite by request content, not filename.

## batch3 page 15 — 'transformer thermal life for Transformer-01' — run r_f3b19721cb
routed=transformer-asset-dashboard/thermal-life EXPECTED=same → routed_ok=YES
asset: re-pin 171 (Transformer-01, gic_15_n3_pcc_01_transformer_01_se). GROUND TRUTH: ZERO temp/thermal/insulation cols; active_power_total_kw REAL ~-940kW (negative=incomer); active_energy_import_kwh ALL NULL (ndistinct=0). 95.0 is NOT a seed (stripped=0.0) → it is a COMPUTED loadFactorPct smeared.
SYSTEMATIC MIS-BIND FABRICATION (all 4 cards) — temp leaves correctly honest-blank, but proxy bindings fabricate impossible values:
- c74 Thermal Life: DEFECT — 'Loss'=969.75 kW is active_power_total_kw (throughput) mislabeled as LOSS (real loss ~1-2%%, not 970kW). Winding/Oil temp honest-blank OK. layer=layer2-emit (proxy mislabel).
- c75 Life & Capacity: DEFECT — lifeRemainingYears bound to fn=loadFactorPct unit=years → 95.0 → '95 YEARS remaining' while lifeBaseYears(const)=20 (remaining>base impossible). Field-binding proof: fields[] lifeRemainingYears kind=derived fn=loadFactorPct unit=years. lifeFillPct=95%% same fn. deratedLoadKva 974.25 real. layer=layer2-emit.
- c76 Thermal Timeline: DEFECT — fields[] slot/loadPct/efficiencyPct ALL kind=bucketed column=active_power_total_kw NO fn → points loadPct=efficiencyPct=slot=-891..-962 (raw NEGATIVE power dumped into %%/time fields). Verdict claims honest_blank yet ships garbage series. Temp legend honest-blank OK. layer=layer2-emit.
- c77 Insulation Aging & Loss of Life: DEFECT — fields[] active_power_total_kw kind=bucketed unit='x' → faa(aging ×)=-891..-962 raw neg power; agingFactor/deltaLolPct=95 (loadFactorPct smear). lolPct/hotspotPeakC/lifeUsedPct honest-blank OK (aei all-null). layer=layer2-emit.
cards_ok=0/4. All 4 = mis-binding fabrication (%-fn→years, raw neg power→%/×/time). Root: layer2-emit chose wrong fn/column for proxy leaves.

## batch3 page 16 — 'ups battery and autonomy for GIC-01-N3-UPS-01' — run r_8cfd3d6cf1
routed=ups-asset-dashboard/battery-autonomy EXPECTED=same → routed_ok=YES
asset: DIRECT resolve (no ambiguity) → mfm 11 GIC-01-N3-UPS-01 CL:600KVA, class UPS, table gic_01_n3_ups_01_p1, 72 cols. GROUND TRUTH: ZERO battery/soc/temp/autonomy cols; active_power_total_kw REAL ~-177..-226kW (neg); voltage_avg ~238-239V, current_avg ~248-251A REAL.
- c50 Battery Health: OK honest_gap — socPct/soc/temp honest-blank w/ reasons (column_absent); Output Voltage 238.56V + Output Current 245A REAL (match DB). Note over-claims 'active power as SOC proxy' but SOC actually blanked (fine).
- c51 Battery Health History: DEFECT — fields[] overall/soc = bucketed active_power_total_kw NO fn unit=score → 'Overall Battery Score' series = raw NEG power -193..-203 (scores must be 0-100); busScore/thermalScore = voltage_avg as 'score' (238). PLUS 'peak temp 35°C' is a SURVIVING STORYBOOK SEED (payload_stripped+raw both contain it; string-embedded dodged strip) on a no-temp meter. verdict falsely render/full 101/101. layer=layer2-emit + card_payloads/strip. ok=false.
- c52 Backup Readiness: OK honest_gap — score/backup-time/headroom/transfer all honest-blank, no fabrication.
- c53 Backup Readiness History: DEFECT — fields[] backup-readiness/backup-time/load-pressure/load-headroom-score ALL bucketed active_power_total_kw NO fn unit=score → 'Autonomy index' series = raw NEG power -185..-204 (0-100 domain). maxY -177 minY -204 negative. layer=layer2-emit. ok=false.
cards_ok=2/4. defects: c51 (power/voltage as battery scores + peak-temp-35 seed), c53 (power as autonomy scores).

## v18 batch1 page 03 — 'energy and power for PCC Panel 1' (r_99879f110d)
- routed: panel-overview-shell/energy-power (EXPECTED), 4 cards, all fill_ok, no payload_error/NaN. 59s.
- card 14 Cumulative Energy: DEFECT [ems_exec/fill] window/label mismatch — periodLabel='Monthly', range='this-month' but value 79,760 kWh = trailing-24h BPDB import delta (DB: month-to-date import Jul1-6 = 76870+76100+78390+78090+80030+3620 ≈ 393k). ALSO import-only total (page-02 pick_mover total for the same window = 93,771 incl UPS export 14.1k) → under-reads panel energy. Real leaves: reactive 1,069 kVArh = BPDB 360 + UPS reactive-import 231+235+244 ✓. Honest '—': target/SEC/markerPct/capacity.
- card 15 Today live power: OK. 845 kVA / 832.1 kW / 40.0 kVAr — DB abs-sums at check: 907.6/901.4/39.1 (kvar exact; kva/kw time-shifted ~40min, plausible). Honest '—': load factor, capacity, worst peak.
- card 16 Energy Consumption Trend: DEFECT [ems_exec/fill] (a) consumer declared range='last-7-days' but rendered only 2 buckets (Jul 05, Jul 06) while DB has 7 full days (Jun 29→Jul 05 deltas 58630/26280/76870/76100/78390/78090/80030); (b) UPS legend "0" + points ups=0.0 false zero (reversed-CT export register moves ~4.7k/day/feeder — same roster.py:102 import-only root cause as page 02). BPDP values real.
- card 17 Daily Power Demand by Feeder: values REAL (hourly ups/bpdp stacks match DB hourly sums; Worst Peak 969.6 'at 05 04:00' = DB exact; legend UPS 544 = 3×181.3 live). DEFECT-minor [payload_db strip]: load-factor stat renders SURVIVING SEED subtext "at 17" ('—' value, seed sub kept) — cmd_catalog.card_payloads.payload_stripped card_id=17 contains '"sub": "at 17" ... "value": 0.0' (seedless-strip missed the subtext leaf).
- DATA-QUALITY (source, not pipeline): BPDB-01 import counter runs ~10x its measured power (1h delta 3480 'kWh' vs avg 351 kW; UPS export counter is 1:1). Energy magnitudes on cards 12/13/14/16 inherit this source scaling; no number-gate flagged it.
- verdict: 2/4 ok (15, 17-with-minor-seed-note... strictly 17 fails seed rule) → counting 17 as defect: 1/4 fully clean + 15 ok.

## v18_08 — 'energy and power for GIC-01-N3-UPS-01' (r_bb525a5212) [batch 2]
- routed individual-feeder-meter-shell/energy-power verbatim = EXPECTED; asset mfm_id=11 correct; 4 cards (39,40,41,42), all exec ok, no payload_error. Bars/series REAL (match neuract 24h buckets; today export delta 331736→331960 = 224≈230 shown).
- DEFECT C [layer2-emit, card 39]: LIFETIME registers bound agg=last into the TODAY donut — reactiveEnergyKwh=22226 (lifetime kvarh register; today's real delta = 11), activeEnergyKwh=0 (import register) beside totalEnergyKwh=230 (correct today-delta via todaysEnergyTotalKwh). Donut Active 0 + Reactive 22226 vs total 230 = incoherent; counter-delta discipline (backend2 parity) not applied by the emit.
- DEFECT D [layer2-emit, card 40]: activePowerAvgKw=95.7 AND reactivePowerAvgKw=95.7 — both bound to fn loadFactorPct (a PERCENT) and shipped as kW tiles (real avgs ≈195 kW / 9.6 kVAr); yMin/demandYMin also = 95.7 via loadFactorWindowPct. Gate rule (iii) replay flags exactly this ("fn 'loadFactorPct' measures load-factor, not power") — bypassed (see DEFECT G). ratedKw 600 = real nameplate (asset_nameplate rated_kva 600, source cmd_equipment_table); contractedKw 486 = config-derived (rated 600 × class contracted_frac) — config-sourced, not seed.
- DEFECT E [layer2-emit, card 41]: hvInputKw = lvOutputKw = 173.1 — ONE meter reading (DB has -173.1 at 01:05:26, real) bound to BOTH sides of an input/output boundary the UPS meter cannot measure; render.reason itself says "hv_input_kw, lv_output_kw not measured by this meter" yet numbers ship (L2 note declares a "stand-in" — a proxy number is NOT honest-blank). expectedLossKwh const 0.0 = derived-zero fabrication. loss/delta/efficiency honest-blank '—' OK.
- DEFECT F [layer2-emit + ems_exec-fill, card 42]: one column smeared over 6 slots — expectedLoad = byte-copy of actualLoad (fabricated expectation), expectedRange max=min=TIME= the power value (executor wrote kW into a time slot — garbage band), anomalies[*] = 25 markers (one per bucket, type/label empty) while dipEvents/surgeEvents const 0 (contradiction; meter HAS sag_event_active/swell_event_active columns for real events); yMax/yMin const 100/0 (%) vs raw signed kW series (-186..-204) → off-scale + sign not normalized.
- DEFECT G [gates, SYSTEMIC — root cause for D/E/F shipping]: source:"$ctx" exempts a field from ALL THREE guards (_reuse_signature returns None on $ctx, _quantity_mismatch returns False on $ctx, _const_without_source returns False on $ctx — gates.py:195/209/235) AND enforce_honest_blank returns [] for is_group_card=True (gates.py:270) — this page (like 07) is ONE group g0, so every card is group-carded and every emit field is $ctx-sourced → the fabrication-guard suite is inert on grouped pages. Replay with is_group_card=False catches card 40 (3 leaves) but still misses 41/42 ($ctx exemption).
- honest gaps OK: card 39 subsidy/target/progress '—' + "Target not configured"; card 41 loss/delta/efficiency '—' with per-leaf reasons.

## batch3 page 17 — 'ups output load capacity for GIC-01-N3-UPS-01' — run r_e02e4237bf
routed=ups-asset-dashboard/output-load-capacity EXPECTED=same → routed_ok=YES
asset: DIRECT → mfm 11 gic_01_n3_ups_01_p1 (UPS 600KVA). GROUND TRUTH: NO input/bypass/rated cols (only frequency_hz, pf_gap_vs_full_load); active_power ~-170..-226kW; current_avg ~248-284A, voltage_avg ~237-239V, frequency_hz ~50Hz REAL. 95.7 & 32.2 NOT seeds (computed).
- c57 UPS Capacity: DEFECT(moderate) — 4 scoreCells but only 2 derivations mislabeled: KVA Score & KW score BOTH fn=kpiKwLoadPctOfRated=32.2 (KVA labeled from kW); Current(I) score & capacityHeadroom BOTH fn=loadFactorPct=95.7 (current-score bound to a load-factor fn; headroom 95.7%% contradicts 32.2%% load). in-domain but mislabel/smear. layer=layer2-emit. ok=false.
- c58 UPS Load: DEFECT — sparkline loadPct bound RAW active_power_total_kw NO fn unit=%% → -195..-198 (neg power as load%%). Load 174kW + PF -0.998 real; Headroom honest-blank; averageLoadPct 95.7 (loadFactorPct, contradicts 32%% load). layer=layer2-emit. ok=false.
- c59 Output Load & Capacity Composite: DEFECT — floor label 'Readiness: 70%%' is a SURVIVING STORYBOOK SEED (in payload_stripped). Real current_avg 284A/voltage_avg 237V/frequency_hz 50Hz shown but RELABELED input/bypass (semantic mismatch, disclosed in note); bypassVoltage + readiness value honest-blank. layer=card_payloads/strip (seed) + semantic relabel. ok=false.
cards_ok=0/3. defects: c57 mislabel/smear scores, c58 raw-neg-power sparkline, c59 'Readiness 70%%' seed.

## batch3 page 18 — 'ups source transfer for GIC-01-N3-UPS-01' — run r_d7be9457fc
routed=ups-asset-dashboard/source-transfer EXPECTED=same → routed_ok=YES
asset: DIRECT → mfm 11 gic_01_n3_ups_01_p1 (UPS). GROUND TRUTH: no transfer/readiness cols; voltage_ll_avg ~412V, current_avg ~246-254A, frequency_hz 50 REAL.
- c54 Transfer readiness: OK honest_gap — Input/Bypass/Sync score all '—', score null; no columns/recovery fns (note). No fabrication. (verdict render/full = 0-data-leaf telemetry quirk.)
- c55 Activity: DEFECT — 'ticks' 30-elem bool array with TWO true transfer events is a SURVIVING STORYBOOK SEED (byte-identical in payload_stripped AND raw seed; ticks NOT in fields[] so never overwritten). Renders 2 FAKE transfer events while count30d/lastTransfer/lifetime all honest-blank (column_absent). Strip zeroed numeric leaves but left the boolean tick array. layer=card_payloads/strip. ok=false.
- c56 Source Transfer Composite: DEFECT — floor 'Readiness: 70%' surviving seed (payload_stripped) + point label bound to active_power_total_kw (raw power 202.38/203.51 as x-axis time label). Real inputCurrent 284A/inputVoltage 411.96V(voltage_ll_avg)/bypassFreq 50Hz relabeled (disclosed); bypassVoltage+readiness honest-blank. layer=card_payloads/strip + layer2-emit. ok=false.
cards_ok=1/3. defects: c55 ticks seed (fake transfers), c56 Readiness-70 seed + power-as-label.

## BATCH 3 SUMMARY (pages 13-18)
All 6 pages routed_ok=YES; assets class-matched (13/14/15 needed re-pin, all DG/Transformer candidates; 16/17/18 direct UPS). infra UP.
SYSTEMIC DEFECTS found:
1. SURVIVING STORYBOOK SEEDS that dodged the strip because string-embedded/boolean (not numeric leaves): 'peak 77%%' (p13 c71), 'peak temp 35°C' (p16 c51), 'Readiness: 70%%' (p17 c59, p18 c56), boolean ticks 2-true (p18 c55). → card_payloads.payload_stripped is NOT fully seedless. layer=card_payloads/strip.
2. MIS-BINDING FABRICATION (layer2-emit): raw active_power_total_kw (often NEGATIVE) bound with NO normalizing fn into %%/score/×/time-label leaves → negative 'percentages'/'scores'/'aging factors'/'axis labels' (p15 c76/c77, p16 c51/c53, p17 c58, p18 c56); and %-fn (loadFactorPct) bound to unit=years leaf → '95 years remaining' (p15 c75); throughput power labeled 'Loss' (p15 c74); single derivation smeared across mislabeled cells (p15 95.0, p17 32.2/95.7).
3. Minor: p14 c79 Worst-Spread derivable stat silently blanked (unbound_by_emit, no per-leaf reason).
CLEAN honest-blanks (correct behavior): all temperature/SOC/tap/transfer leaves honest-blanked WITH per-leaf reasons where the meter lacks the column.

## v18_09 — 'power quality for GIC-01-N3-UPS-01' (r_1bc17049b9) [batch 2]
- routed individual-feeder-meter-shell/power-quality verbatim = EXPECTED; asset mfm_id=11 correct; 3 cards (47,48,49), all exec ok, no payload_error.
- card 47 PASS (honest_gap): iThd 9.0 real (thd_compliance_i_avg; DB 7.5-8.3 at nearby ts), vThd/h5/h7/flicker/crest null = VERIFIED honest (thd_voltage_*/harmonic_5th/7th 0 of 3523 rows in 24h; no flicker/crest columns); limits 8% = IEEE-519 config. L2 note wording promises "representative current harmonics (H5,H7)" that are actually null — wording wart only, leaves honest.
- DEFECT H [layer2-emit, card 48]: default distortionProfile.view stays 'v-thd' (byte-copy of default) whose series is EMPTY (V-THD unmeasured) while the REAL I-THD series (R/Y/B 4.4-9.2%, matches thd_current_*_pct) hides behind the toggle — the emit's own note says "Showing I-THD time-series trends" but it never morphed `view`. Card opens blank; render verdict still claims answerability=full/leaf_stats 75/75 real (verdict counts filled leaves, ignores the active view). Seed chrome labels "Max: 480V"/"Min: 410 V"/"Max: 480A" survive as maxLine/minLine label text (values null).
- DEFECT I [layer2-emit, card 49]: k-stress view's "K - factor" stat+series filled with kpi_displacement_pf (≈ -0.998) — displacement PF shipped under a K-FACTOR label (K-factor is a ≥1 harmonic-derating quantity; a NEGATIVE 'K-factor' is impossible), with const K-Watch 1.0 reference line drawn against it (yAxisLabel morphed to 'PF Scale' but stat label/view name still claim K). Signed raw PF (-0.998) and pf_gap -1.99 shipped unnormalized — VERIFIED these ARE the raw DB column values (power_factor_total=-0.998, pf_gap_vs_full_load=-1.9906 — upstream sign convention), so real-but-operator-hostile; the mislabel is the defect, not the values. true PF 0.996 / phase angle 176-177 / PF target 0.95 real/config ✓.

## v18 batch1 page 04 — 'harmonics and power quality for PCC Panel 1' (r_a68ae6e694)
- routed: panel-overview-shell/harmonics-pq (EXPECTED), 5 cards. 168s.
- card 23 KPI strip: OK. iThd events=1, neutral=1, total=2 REAL (DB: ups1 thd_current_y 9.6%; bpdb neutral_stress_event_active=1, current_neutral=120.8A). worstIThd {kw 169.6, pf 0.996, iThd 9.0} matches gic_01_n3 (9.5/9.6/5.7). vThd/h5/h7/kFactor null = HONEST (DB thd_voltage_* and harmonic_5/7 100% NULL, 0 of 3523 rows). Note: presentation leaf 'decimals'='—' (config over-strip, cosmetic).
- card 24 Timeline: DEFECT [layer2-emit] payload_error='llm call failed (timeout): timed out (prompt≈23415 tok)' — L2.card id=24 fail=llm_timeout, conforms=False, note='AI emit unavailable (transport failure)'. Data leaves still real (24/38: panels kw/pf/iThd match DB); limits all null (no threshold lines). Known big-emit-timeout family; fail-fast worked but contract (e) violated.
- card 25 AI Summary: DEFECT [layer2-emit] FABRICATED ZEROS — stats block ALL 0.0 (iThd/vThd/pfGap/total/neutral=0.0, worst.kw=0.0, panels[].kw=0.0…) while sibling card 23 in the SAME RUN shows total=2 real issues → renders a false '0 issues' story. Root cause visible in ai_r_a68ae6e694.jsonl call#5: the emit's exact_metadata echoes the payload_stripped zero-placeholder skeleton as if it were metadata; executor left all 55 data leaves undeclared (render leaf_stats undeclared=55, verdict honest_blank — telemetry knows, payload lies).
- card 26 Feeder PQ table: OK. period.panels real (kw 169.6/pf 0.996/iThd 9.0), honest nulls DB-verified. Title '{period}' is composed by the component (titlePrefix+connector+period.label='Now') — not a defect.
- card 27 Signature: OK. Same real panels block; vThd/h5/h7 honest-null; note 'decimals'='—' config over-strip cosmetic.
- verdict: 3/5 ok; defects card 24 (payload_error/emit timeout), card 25 (zero-fabrication via emit echo).

## v18_10 — 'dg voltage and current for DG-1' (r_c7938ef357, asset_pending → pinned mfm_id=2) [batch 2]
- run 1: asset_pending=True, 2 candidates BOTH class DG (DG-1 MFM id 2 has_data; GIC-28-N1-DG-01 [Jackson] id 300 no data) — correct ambiguity surface. Re-POST pinned asset_id=2 (how=user-choice) → same run_id r_c7938ef357 (response file OVERWRITTEN — pinned copy saved as v18_10b.json; the pending copy as v18_10.json). Routed diesel-generator-asset-dashboard/voltage-current verbatim = EXPECTED. 4 cards (66,67→44 swap,68,69).
- GROUND TRUTH (neuract.dg_1_mfm, 17276 rows/24h): DG on STANDBY — max(current_r)=max(voltage_ry)=max(power)=0 over 24h; current_unbalance_pct & voltage_ll_unbalance_pct 0 of 17276 (never logged); kpi_voltage_deviation_pct = -100 (dead bus); energy register 27727.707 real. So the page's 0.0 V / 0.0 A / all-zero series are REAL MEASURED ZEROS, not fabrication — adversarial zero-check PASSES.
- card 66 PASS (honest_gap): phase L-L 0.0 real, L-N avg 0.0 real, Unbalance/Spread '—' VERIFIED honest (columns never logged). WART: unit 'kV' chrome on an LT 415V DG (default HT chrome; moot at 0.0). Reason "voltage_avg not measured" TRUE (table has voltage_ln_avg/ll_avg instead).
- DEFECT J [ems_exec-fill, card 67→44]: 12 Storybook SEED event skeletons survive (default card-44 payload has exactly these 12 {color,index,seriesLabel} entries; fill nulled index but kept the 12-item fan-out — ghost swell/normal event rows for a DG with ZERO events; no sag/swell columns exist on dg_1_mfm). Card 69 shows the correct treatment (events: []). Series/stats otherwise honest (zeros real, Max/Min '—').
- card 68 PASS (honest_gap): currents/neutral/avg 0.0 real; Unbalance '—' honest. WART: render.reason claims "current_r/y/b/avg — no valid reading in this window" while real zeros shipped — telemetry contradicts the (correct) render.
- card 69 PASS (honest_gap): all-zero series real; Max Unbalance '—' VERIFIED honest; yTicks [-1..1] = honest padding around a true-zero series; events [] correct.

## v18 batch1 page 05 — 'voltage and current for PCC Panel 1' (r_b57a82feb3)
- routed: panel-overview-shell/voltage-current (EXPECTED), 5 cards, all fill_ok, no payload_error. 99s.
- card 18 Events KPI Strip: DEFECT [ems_exec/fill] — filterSelection.preset='today' but current-events=0 while DB (gic_01_n8_bpdb_01_p1) has 32 current_imbalance rising edges TODAY and flag=1 in the 00:54 row; neutral=1 counted but current=0 → instant-state sampling of a flapping register presented as a 'today' event count. Real leaves: worstCurrent/worstVoltage blocks (neutralA 59.7, iUnb 5.23, vDev -0.92, truePf 1.004 — DB kpi_true_pf max today 1.0138, >1 is SOURCE meter artifact not fabrication).
- card 19 AI Summary: DEFECT [layer2-emit] — same zero-skeleton fabrication as page-04 card 25: stats sag/swell/current/neutral/total ALL 0.0, panels ups-01..03 all-0.0; contradicts card 18 total=1 in same run; 41/41 leaves undeclared, verdict honest_blank but payload ships zeros.
- card 20 Event Timeline: DEFECT [ems_exec/fill] — today buckets '00:00'/'01:00' render current=0.0/neutral=0.0 events while DB shows 25+6 current and 20+5 neutral rising edges in those hours (flags flap 18-29 edges EVERY hour — no debounce/no aggregation binds them). iWorst/vWorst series + panels block real.
- card 21 Current Distribution: OK (rendered metric amps real: 262/244/255/707; GIC-02 members amps=null honest). NOTE: unused leaves zero-padded (vAvg/vMax/vMin=0.0, table='', sag/swell 0.0) — should be honest-null; not rendered by this component.
- card 22 Other Panels Event: DEFECT [ems_exec/fill] — per-panel sag/swell/current/neutral ALL 0.0 including bpdb, contradicting card 18 (neutral=1, worst=bpdb) same run + DB events; electrical leaves (amps/vAvg/neutralA/iUnbalance/vDeviation) real.
- verdict: 1/5 ok. Event-count binding is the page's systemic failure; AI-summary zero-skeleton repeats.

## v18 batch1 page 06 — 'voltage and current for GIC-01-N3-UPS-01' (r_aea5abb769)
- routed: individual-feeder-meter-shell/voltage-current (EXPECTED); asset pinned by AI directly: GIC-01-N3-UPS-01 mfm_id=11 class=UPS, no picker round-trip needed. 4 cards, all fill_ok, no payload_error. 46s.
- card 43 Voltage Live Health: OK. Phases 237.2/237.3/241.0 vs DB 237.7/237.7/241 ✓; unbal 1.05 vs 0.92 ✓; avg 238.5 vs 238.8 ✓; deviation -0.625 = meter kpi_voltage_deviation_pct family ✓. NOTES: 'Max gap'='—' while sibling card 45 derives its gap (20.0) from the same-shape phases (inconsistent derivation coverage); summary pairs L-N actual 238.5 V with nameplate L-L 'Nominal 415' (semantic mispair, both values real).
- card 44 Voltage History: DEFECT [ems_exec/fill] — (a) 'Worst Spread' = 239.9999 V FABRICATED: DB 25h per-row phase spread ≤ ~5 V, cross-window extremes 241-223.5=17.5 V — nothing measures 240 (looks like nominal minus ~0); (b) 'Max Deviation'='—' though the meter LOGS kpi_voltage_deviation_pct (25h max |5.96|) → blank-where-measured, no reason; (c) xLabels = 10 empty strings for 25-point series (axis unbound); (d) 12 event markers with index=null while DB shows 0 sag/swell rising edges today (skeleton junk). Series REAL (25 hourly means 227-241 V match DB range).
- card 45 Current Live Health: OK. R/Y/B 240/230/250 vs DB 243/235/253 ✓; N 17.32 vs 15.6 ✓; unbal 4.167 (=(250-240)/240) vs DB 4.115 ✓; neutral/phase 7.22 vs 6.43 ✓; Max gap 20 ✓ derived.
- card 46 Current History: DEFECT [ems_exec/fill] — stats bound to the LIVE snapshot, not the history: 'Peak Current' 250.0 vs own series max ~290.5/maxY 302.4/DB 25h max current_r=325; 'Neutral Peak' 250.0 vs DB 25h max current_neutral=25.98 (≈10x, bound to phase peak) — hard mis-bind; 'Average Current' 240.0 = live snapshot; xLabels 10×''. Series REAL (hourly means ~260-290 A).
- verdict: 2/4 ok; history stat-leaf mis-binding is the page's defect family.

## v18_11 — 'dg engine and cooling for DG-1' (r_dd90453138, asset_pending → pinned mfm_id=2) [batch 2]
- run 1 asset_pending (same 2 DG candidates), re-POST asset_id=2 → same run_id, pinned copy = v18_11b.json. Routed diesel-generator-asset-dashboard/engine-cooling verbatim = EXPECTED. 3 cards (60,61,62).
- DEFECT K [DB/data-layer + reason wiring, card 60 Engine 3D Callout Viewer]: whole-card honest_blank (object null, viewer {}) although a DG engine-callout model IS registered — cmd_catalog.asset_3d_registry 'dg-final-v2' ("used by the Engine 3D Callout Viewer (card 60)") and /home/rohith/CMD_V2/public/models/dg_final_v2.glb exists (985 KB). The L2 asset_3d resolver (layer2/emit/metadata/asset_3d.py 4-tier) reads neuract.lt_asset_3d + lt_mfm.asset_3d_override_id + lt_mfm_type.default_asset_3d_id — ALL EMPTY (lt_asset_3d count 0, asset_3d_model count 0, override/default ''), no viewer_policy app_config rows → avoidable blank. Degrade itself honest (no fabricated model) BUT the reason shipped is the WRONG template: "these metrics not logged by this meter." for a missing 3D binding. Bonus registry wart: lt_mfm 2 'DG-1 MFM' has mfm_type 'LT Panel'.
- DEFECT L [layer2-emit, card 61 Thermal Timeline]: DECLARED PROXY SHIPPED — KPIs "Peak Exhaust 0.0 °C" and "Max Coolant 0.0 °C" filled via fn worstPeakKw (a POWER fn; DG measures NO temperature — contract requires '—' + reason); 2 ghost events with value 0.0 °C via the same fn (idx '—'); const band 85-110 °C "Expected Range" (metric thresholdWarn/thresholdTrip, source const) = INVENTED thresholds with no DB source (rule-iv class, bypassed per DEFECT G); 4 electrical proxy series (power/freq/PF/current) bound at unresolvable slot 'chart.series' — they FAILED to fill (series [] — the only reason kW lines aren't drawn on the thermal chart). L2 note openly declares the proxy intent ("electrical metrics as proxies for thermal history") — mandate breach at emit level.
- DEFECT M [layer2-emit, card 62 Pressure·Speed·Load]: "Peak Load 0.0 %" via worstPeakKw (kW fn in a % slot — numerically right only because the DG is off); const band y1=y2=0.0 kPa (degenerate zero "Expected Range"); legend Speed bound to metric dg_engine_speed_rpm fn loadFactorPct (absurd; shipped '—' only because the fn refused). Oil-P/events '—' honest ✓.
- Note: the '0.0' electrical zeros elsewhere are REAL (DG standby, see v18_10 ground truth).

## v18 batch1 SUMMARY (pages 01-06, all sequential, host untouched)
- Routing: 6/6 pages routed to the EXPECTED page_key; asset resolution 6/6 correct (PCC-Panel-1 mfm 317 ×5, GIC-01-N3-UPS-01 mfm 11 ×1), zero asset_pending round-trips.
- Cards: 28 total, 16 ok / 12 defective. No infra_down; neuract :5433 up throughout.
- SYSTEMIC DEFECT FAMILIES (cross-page):
  1. Reversed-CT energy false-zeros [ems_exec/fill]: UPS members render kwh=0.0 wherever per-member energy binds import-only (cards 12,13,16) — roster.py:102 lacks the pick_mover fix that members.panel_kwh:140 already has. Panel totals are right; member leaves lie.
  2. AI-Summary zero-skeleton [layer2-emit]: narrative PQ/event summary cards (25, 19) ship exact_metadata echoing the payload_stripped 0.0-placeholder skeleton → renders a false '0 issues' story while sibling KPI cards in the SAME run show real counts. Telemetry says honest_blank/undeclared; payload says 0.0.
  3. Event-count binding [ems_exec/fill]: *_event_active registers flap 18-29 edges/hour on bpdb but cards 18/20/22 render 0 events for 'today' (instant-state or unbound), contradicting the meter's event registers.
  4. History stat mis-binds [ems_exec/fill]: history cards' stat leaves bound to the live snapshot or wrong column (card 46 Neutral Peak 250 A vs real 26 A; card 44 Worst Spread 240 V), while their series are real.
  5. Window/label mismatches [ems_exec/fill]: card 14 'Monthly' label on a 24h delta; card 16 'last-7-days' renders 2 buckets (7 days exist in DB).
  6. One emit timeout payload_error (card 24, 23.4k-tok prompt, fail-fast worked, contract (e) still violated).
  7. Composite rail under-fill (card 7): rail quickStats '—' while card 11 fills identical metrics in the same run.
  8. Seed survivor: card 17 'at 17' subtext lives in card_payloads.payload_stripped (strip missed a subtext leaf).
- DATA-QUALITY (source, NOT pipeline): BPDB-01 import counter ~10x its power (3480/h vs 351 kW avg); kpi_true_pf logs >1 (max 1.0138). No number-gate flags these.
- Fully verified REAL (byte/value-match to neuract): card 10 25-pt series == DB hourly aggregate; cards 43/45 live health == DB rows minutes apart; card 17 hourly demand stacks; card 11 quick stats; PQ worst blocks (23/26/27); BPDB energy deltas.
- CORRECTION to the count above: 28 cards total, 14 ok / 14 defective (p01 7/8, p02 0/2, p03 1/4, p04 3/5, p05 1/5, p06 2/4).

## v18_12 — 'dg fuel efficiency for DG-1' (r_1f97dfa47f, asset_pending → pinned mfm_id=2) [batch 2]
- run 1 asset_pending (same 2 DG candidates), re-POST asset_id=2 → pinned copy v18_12b.json. Routed diesel-generator-asset-dashboard/fuel-efficiency verbatim = EXPECTED. 3 cards (63,64,65).
- card 63 Fuel Tank Anatomy: EVERY leaf null INCLUDING title/subtitle chrome; render verdict 'render' with reason None and leaf_stats 0/0/0 — honest VALUES (no fuel channels on dg_1_mfm — true) but ZERO per-leaf reasons shipped (contract requires '—' + reason) and static chrome (title) lost; di.fields = [] entirely. dg-v1 fuel-tank model is registered for this card in asset_3d_registry (same empty-neuract-catalog issue as DEFECT K). ok=false [validate/render + layer2-emit].
- card 64 All Runs PASS (honest_gap): totalKwh 0.0 = REAL today-delta (register 27727.707 flat, DG never ran); starts/avgLoad/runHours/totalFuelL/faults null honest + L2 note declares them unmeasured. (Nonsense bindings starts←loadFactorPct agg=count refused honestly.) WART: reason "active_power_total_kw — no valid reading in this window" again mislabels real standby zeros.
- DEFECT N [layer2-emit + ems_exec-fill, card 65 Fuel & Tank Composite]: legend shows the LIFETIME ENERGY REGISTER 27727.70703125 as "Level %", "Rate L/hr" AND "Temp °C" — one register smeared across three unmeasured quantities. Emit bound legend[0]←active_energy_import_kwh(last), legend[1]/[2]←active_power_total_kw(last)=0 real — but ALL THREE shipped 27727.707, so the executor also wrote the wrong binding's value (fanout smear). Cost KPI const 0.0 ₹/kWh (metric dg_cost_per_kwh, no DB source) = fabricated zero; 2 ghost events value 0.0 (const metric 'insight'); band y1=y2=0.0 degenerate. series[] stayed EMPTY (fill failed on series[i].values — accidentally prevented the 27727-line on a 0-105% axis). Efficiency/SFC/Load '—' honest.
- batch 2 COMPLETE (pages 07-12). Recurring systemics: (1) DEFECT G group/$ctx gate bypass lets emit proxies/consts ship on every grouped page; (2) seed axis scaffolds (yTicks/yLabels/bands) never recomputed for tick-only charts; (3) DG proxy-emits ("X as a proxy for Y") violate the honest-blank mandate at emit level even when fills accidentally refuse; (4) neuract 3D catalogs empty while cmd_catalog.asset_3d_registry is populated (avoidable 3D blanks); (5) ai_log run_id is global — parallel batches interleave AI-call logs.

## cross batch — CROSS-CLASS / EDGE prompts (cross_1..cross_9, pages/cross_<i>.json) [2026-07-06 01:29-01:30]
Focus: homonym pins, candidate recall, class-appropriate routing, sparse/dead honest-blank, NaN/seed. 8/9 prompts correctly SHORT-CIRCUIT to the AssetPicker (asset_pending, Layer 2 NOT run, 0 cards, no errors); 1/9 (AHU-5, unique in registry) confident-pins and renders 4/4 cards live.

Per-prompt verdicts:
- cross_1 r_ea44a73ed2 'Real-time power of DG-03 Jackson' — OK (picker). candidates=[4 DG-3 MFM, 302 GIC-28-N3-DG-03 [Jackson]]; named Jackson asset IS offered; no mis-pin. host.log `[r_ea44a73ed2] 1b ... candidates=2 how=ambiguous class_prior=DG`. Page diesel-generator-asset-dashboard/operations-runtime = class-appropriate. OBSERVATION (not defect): the 'Jackson' qualifier uniquely names id 302 — 1b could confident-pin; conservative picker is contract-safe.
- cross_2 r_a280d5c50b 'Load profile of UPS-04 over the last 24 hours' — OK (picker). All 3 registry UPS-04 homonyms offered (191, 299, 23). ups-asset-dashboard/output-load-capacity appropriate.
- cross_3 r_c1bb1de592 'UPS-01 load percentage right now' — OK (picker). All 5 registry UPS-01 homonyms offered (11, 188, 192, 194, 296).
- cross_4 r_b69bd1fbae 'Show voltage levels for Transformer-03' — OK (picker). Offered 173 [Secure Elite300] + 100176 PQM; omitted registry row 167 GIC-15-N12 is CORRECT filtering — its table gic_15_n12_pcc_02_transformer_03_sch does NOT exist in neuract (offering it would be a dead meter); offered 173 verified LIVE (30392 rows/7d, max ts now). individual-feeder-meter-shell/voltage-current appropriate (transformer deep-tabs are only tap-rtcc/thermal-life).
- cross_5 r_c94382a4f9 'Show voltage for UPS-10' — OK (picker). Both UPS-10 homonyms offered (78, 236). Feeder voltage-current shell appropriate (ups-asset-dashboard has no voltage page).
- cross_6 r_ab957fb3ac 'real-time power and current for Transformer 01' — OK (picker). Offered 171 + PQM 100174 + 306 33KV Main; omitted 164 GIC-15-N10 correct (relation gic_15_n10_pcc_01_transformer_01_sch does not exist); 171 verified LIVE (30455 rows/7d).
- cross_7 r_102b506a1f 'energy consumption of Transformer-05 today' — OK (picker). Complete recall: 263 + 100178 are the only Transformer-05 meters in lt_mfm. individual-feeder-meter-shell/energy-power appropriate.
- cross_8 r_5caef922fc 'power quality for a spare feeder' — OK (picker). 1b candidates=46, response carries ALL 46 spare feeders (not truncated); class_prior=None sensible; individual-feeder-meter-shell/power-quality appropriate.
- cross_9 r_92a2bfb0ae 'voltage and current health for AHU-5' — PASS WITH DEFECTS (below). Unique pin GIC-03-N6-AHU-5 (mfm_id=36, `1b ... candidates=0 how=AI class_prior=AHU basket_cols=61`), validate pass, 4/4 cards exec ok, rendered=4 partial=4 blank=0, zero NaN/Inf across all payloads, payload_error=None all cards. Cards 43/45 live health VERIFIED REAL vs neuract rows minutes apart (V 244.5/243.4/247.0 ~ DB 244.6/243.8/246.6; I 47/48/55 N=7.55 ~ DB 47/49/54-55 N=6.24-7.21; unbalance/spread/neutral-ratio all track). Card 44 25-pt hourly series real (236-245 V band).

- DEFECT O [layer2-emit, cross_9 card 46 Current History, MEDIUM]: "Neutral Peak" stat BOUND TO THE WRONG METRIC — emit declared stats[3].value metric=current_max/column=current_max label='Neutral Peak' (ai_r_92a2bfb0ae.jsonl call 6; current_neutral WAS present in the emit request context). Renders 55.0 A as neutral peak; DB ground truth max(current_neutral) over the exact L2 window (2026-07-05T01:30:49+05:30 → 2026-07-06T01:30:49) = 10.535654 A. A real number for the wrong quantity = fabrication-class defect. Same emit also binds 'Peak Current' and 'Max Unbalance' with agg='last' (label says peak/max; DB window max 57 A / 14.29% vs shipped 55 / 10.0) — label-vs-agg semantics wart, same family.
- DEFECT P [ems_exec-fill reason, cross_9 card 44 Voltage History, LOW-MED]: honest-blank with a FACTUALLY FALSE reason. render.gaps: slot stats[0].value fn=voltageStatutoryBand cause=no_reading reason 'voltage_avg, kpi_voltage_deviation_pct — no valid reading in this window' — but neuract holds 3116/3116 non-null rows for BOTH columns in that exact window (max voltage_avg 247.07, max kpi_voltage_deviation_pct 2.944). Root cause: ems_backend.metrics fetched only [voltage_r_n,voltage_y_n,voltage_b_n], so the derived fn had no inputs; 'metric not fetched' mislabelled as 'no valid reading' (recurs from batch-2 card 64 wart).
- DEFECT Q [producer/emit seed residue, cross_9 card 44, LOW]: events = 12 Storybook seed event STUBS (sag/swell colors + R/Y/B seriesLabels) with every index=null; _emit_gaps records history.data.events 'unbound_by_emit'. Data leaves honestly nulled (no fake positions) but the seed skeleton (event count/type/phase distribution) survives; unbound events should collapse to [].
- DEFECT R [derived-zero const, cross_9 card 46, LOW]: maxLine.value = minLine.value = 0.0 from const metrics expected_max_a/expected_min_a with '—' labels — zero band-lines on an amps chart; card 44 handles the same missing consts honestly (null). Inconsistent const-missing handling → derived-zero.
- Batch summary: 9/9 no wrong-asset pin, no cross-asset data leakage, recall complete for every named asset (verified vs lt_mfm; omissions = meters with no backing table), routing class-appropriate on all 9, zero NaN, zero payload_error. Defect families all inside the one rendered run: wrong-metric emit bind (O), false no_reading reason on under-fetched derived inputs (P), seed-stub residue on unbound arrays (Q), derived-zero consts (R).

================================================================================
# FINAL VERIFICATION MATRIX — fullsweep_20260706_004334 (18-page sweep + 9 cross-class) — 2026-07-06
This is the AUTHORITATIVE consolidated matrix for the fresh-rehost session (preflight 00:43 IST, logs/ cleared at start). It SUPERSEDES the partial 13-page matrix above (which predated the 02-06 re-runs; those logs are now present).
================================================================================

## (1) 18-PAGE x CARD MATRIX
| nn | page | run_id | ok/total | routed_ok | DEFECTS (layer + log evidence) | honest gaps (reason) | infra |
|----|------|--------|----------|-----------|-------------------------------|----------------------|-------|
| 01 | panel-overview/real-time-monitoring | r_f9787f915f | 7/8 | YES | c7 [ems_exec/fill] rail blanks metrics live in same run (pipeline_r_f9787f915f L2.card id=7 endpoint=None vs id=11 real), no per-leaf reasons | c5 8 feeders source-empty (DB-verified); c9 no capacity denominator | no |
| 02 | panel-overview/energy-distribution | r_075d05bffb | 0/2 | YES | c12,c13 [ems_exec/fill] reversed-CT import-only -> false 0.0 kWh on live 200kW feeders + 79670-vs-93771 self-contradiction (roster.py:102 import-only vs members.py:140 pick_mover; DB export deltas +4691/+4703/+4706) | incomer tables empty/nonexistent; loss/efficiency '-' | no |
| 03 | panel-overview/energy-power | r_99879f110d | 1/4 | YES | c14 [ems_exec/fill] 'Monthly' label on 24h delta (79,760 vs MTD 393k); c16 [ems_exec/fill] last-7-days renders 2/7 buckets + UPS false-zero; c17 [payload_db strip] seed sub 'at 17' (card_payloads.payload_stripped c17) | target/SEC/capacity/load-factor '-'; HHF legend | no |
| 04 | panel-overview/harmonics-pq | r_a68ae6e694 | 3/5 | YES | c24 [layer2-emit] payload_error llm_timeout ~23.4k-tok (pipeline_r_a68ae6e694 fail=llm_timeout) — the sweep's ONLY payload_error; c25 [layer2-emit] zero-skeleton echoed as exact_metadata -> false '0 issues' vs sibling c23 total=2 (ai_r_a68ae6e694 call#5) | vThd/h5/h7/kFactor 0/3523 rows | no |
| 05 | panel-overview/voltage-current | r_b57a82feb3 | 1/5 | YES | c18,c20,c22 [ems_exec/fill] *_event_active registers never bound: 0 rendered vs 25-32 DB rising edges today; c19 [layer2-emit] zero-skeleton false '0 events' | GIC-02 members null (empty tables) | no |
| 06 | feeder/voltage-current | r_aea5abb769 | 2/4 | YES | c44 [ems_exec/fill] fabricated 240V 'Worst Spread' (DB spread <=17.5V) + measured deviation blanked + xLabels 10x''; c46 [ems_exec/fill] history stats = live snapshot, Neutral Peak 250 vs DB 25.98 (10x phase mis-bind) | c43 Rate Change '-' | no |
| 07 | feeder/real-time-monitoring | r_82157379cd | 0/3 | YES | c36 [fill+emit] seed yLabels axis + projectedDemand=byte-copy of activePower; c37 [fill] seed yTicks 430-390 -> live 228-240V off-scale + seed 420/400V threshold text; c38 [emit+gates] seed 120/100A thresholds vs 254-305A live, gates skipped (is_group_card, gates.py:270; ai_r_44796d791a e18 replay proves rule-iv would catch) | c36 activeEnergy 0 = real import register | no |
| 08 | feeder/energy-power | r_bb525a5212 | 0/4 | YES | c39 lifetime registers as today's donut (22226 vs real delta 11); c40 loadFactorPct% as kW tiles (95.7 both); c41 one reading as both HV+LV + const loss 0.0; c42 expected=actual copy + kW in time slots + 25 ghost anomalies + %-axis on signed kW [all layer2-emit; SYSTEMIC: $ctx fields exempt from all 3 honesty guards + is_group_card skips pre-pass] | subsidy/target '-'; loss leaves reasoned | no |
| 09 | feeder/power-quality | r_1bc17049b9 | 1/3 | YES | c48 [layer2-emit] view left on EMPTY v-thd while real i-thd behind toggle (note contradicts payload) + seed 480V/410V/480A chrome; c49 [layer2-emit] displacement PF -0.998 shipped as 'K-factor' + const K-Watch 1.0 | c47 vThd/h5/h7/flicker/crest truly unlogged (0/3523) | no |
| 10 | dg/voltage-current | r_c7938ef357 | 3/4 | YES | c67 [ems_exec-fill] 12-entry Storybook seed event skeleton (ghost rows) instead of [] on zero-event DG | standby zeros REAL (DB max=0/17276 rows); unbalance cols never logged | no |
| 11 | dg/engine-cooling | r_dd90453138 | 0/3 | YES | c60 [DB] neuract lt_asset_3d/asset_3d_model 0 rows while dg-final-v2 registered+glb exists -> avoidable blank + wrong reason template; c61 [layer2-emit] power-fn as degC KPIs + invented 85-110degC band; c62 [layer2-emit] kW fn in % slot + 0-0 kPa band + rpm<-loadFactorPct | c60 no fabricated model; oil-P/avg-load/events '-' | no |
| 12 | dg/fuel-efficiency | r_1f97dfa47f | 1/3 | YES | c63 [validate+emit] all-null incl. title chrome, ZERO per-leaf reasons, di.fields=[]; c65 [emit+fill] lifetime register 27727.707 smeared as Level%/Rate/Temp + Cost 0.0 const + ghost events | c64 run-hours/fuel/starts/faults reasoned; fuel channels truly absent | no |
| 13 | dg/operations-runtime | r_44796d791a | 3/4 | YES | c71 [card_payloads/strip] seed 'peak 77%' sub rendered beside '-' value | c70/c72/c73 DG-idle blanks w/ reasons | no |
| 14 | transformer/tap-rtcc | r_d06f6da969 | 3/4 | YES | c79 [layer2-emit] 'Worst Spread' unbound_by_emit, no user-facing reason, though derivable (maxY-minY=316V) | c78/c80/c81 zero tap/OLTC columns (column_absent); c79 Max Deviation garbage-scale col | no |
| 15 | transformer/thermal-life | r_f3b19721cb | 0/4 | YES | c74 throughput 969.75kW labeled 'Loss'; c75 loadFactorPct as YEARS -> '95 years remaining' > 20yr base; c76 raw negative power in loadPct/efficiencyPct/slot; c77 raw negative power as aging factor faa + 95.0 smear [all layer2-emit, di.fields cited] | winding/oil/hotspot/insulation blanks correct | no |
| 16 | ups/battery-autonomy | r_8cfd3d6cf1 | 2/4 | YES | c51 [emit+strip] negative power/voltage as battery scores + seed 'peak temp 35C' + false render/full verdict; c53 [emit] negative power as autonomy scores | c50 SOC/temp column_absent; c52 all readiness leaves blank | no |
| 17 | ups/output-load-capacity | r_e02e4237bf | 0/3 | YES | c57 [emit] 4 score cells = 2 smeared derivations (32.2 x2, 95.7 x2; headroom contradicts load); c58 [emit] raw negative power as sparkline loadPct; c59 [strip] seed 'Readiness: 70%' | c58 headroom; c59 bypassVoltage/readiness | no |
| 18 | ups/source-transfer | r_d7be9457fc | 1/3 | YES | c55 [strip] boolean ticks seed -> 2 FAKE transfer events (payload_stripped byte-identical); c56 [strip+emit] seed 'Readiness: 70%' + raw power as x-axis time label | c54 all transfer scores reasoned; c56 bypass/readiness | no |

## (2) TOTALS + DEFECT FAMILIES
- Cards served: 70 (18 pages). **OK = 28/70 (40%). DEFECT cards = 42/70.** Misroutes = **0/18** (+0/9 cross). Infra-blocked = **0**. Honest-gap-carrying cards = 33 (39 gap line-items) — every claimed gap DB-verified honest (column absent / table empty / register flat), all with per-leaf reasons EXCEPT c7 and c63 (their absence IS the defect).
- FAMILIES (a card may appear in >1):
  - **A fab-by-zero / derived-zero (13):** 12,13,16,18,19,20,22,25,41,42,61,62,65 (+cross_9 c46 zero band-lines)
  - **B surviving seed (11):** 17,36,37,38,48,51,55,56,59,67,71 (+cross_9 c44 event stubs)
  - **C false-blank (5):** 7,44,48(view),63,79 (+cross_9 c44 false 'no_reading' reason)
  - **D misroute (0):** none — 18/18 + 9/9 class-appropriate
  - **E legend/unit leak (4):** 14(Monthly-on-24h),49(K-factor),65(Level/Rate/Temp),74('Loss') — warts: c43 415-nominal-vs-L-N, c66 kV chrome (both PASS)
  - **F emit-timeout (1):** 24 — the sweep's only payload_error
  - **G semantic mis-bind (19):** 36,39,40,41,42,46,49,51,53,56,57,58,61,62,65,74,75,76,77 (+cross_9 c46 Neutral Peak<-current_max) — THE DOMINANT FAMILY; root causes: layer2-emit proxy-binds an available-but-wrong-quantity column (overwhelmingly signed active_power_total_kw) instead of honest-blanking, AND the gates bypass ($ctx-source exemption gates.py:195/209/235 + is_group_card short-circuit gates.py:270) lets it ship ungated.
- SYSTEMIC root causes ranked: (1) gates $ctx/group bypass [enables G+A on pages 07/08/11/12/15/16/17]; (2) emit cross-quantity binding discipline; (3) payload_stripped strip incompleteness for string-embedded numbers/booleans/tick-arrays [B]; (4) event-register binding never implemented in fill [05 family]; (5) reversed-CT import-only roster energy [02/03]; (6) empty neuract 3D catalogs [c60/c63].

## (3) FRAMES=PAYLOADS GATE + RENDERER COVERAGE (preflight, confirmed post-sweep)
- **FRAMES=PAYLOADS: CLEAN.** Zero offenders in host/web fill/** — all grep hits triaged (comments on the deleted path / type-only ChartFilterParams import / CMD V2's own empty-scaffold + direct payload overlay). Post-sweep: **0 `_frame_` keys** in all served pages (v18_*.json + cross_*.json); the payload IS the vm/props.
- **Renderer coverage: PASS.** 18 routable_pages (4 DG + 4 feeder + 5 panel-overview + 2 transformer + 3 UPS); 70 distinct card_ids in page_layout_cards; registry = COMPONENTS(58) u COMPOSE{5,6,160} u SPECIAL{8,28,60} u FILL(43) = 71 ids — every card_id resolves, zero missing, zero duplicate CARDS keys. Every served card mounted its REAL CMD_V2 component (0 whole-card refuse, 0 NaN/Infinity anywhere).
- payload_error scan: 1 non-null in the whole sweep (c24 llm_timeout, family F).

## (4) CROSS-CLASS VERDICT
9/9 PASS on routing/pinning: zero wrong-asset pins, zero cross-asset data leakage, homonym recall COMPLETE for every named asset (verified vs lt_mfm; the only omissions 167/164 have no backing neuract table — correct filtering), class-appropriate shell every time, picker conservative-but-safe ('Jackson' could confident-pin — observation, not defect). The one fully-rendered run (cross_9 AHU-5, r_92a2bfb0ae, unique pin, 4/4 cards) confirmed live values REAL vs neuract minutes apart, zero NaN/payload_error — but reproduced the SAME main-sweep families in miniature: O wrong-metric bind (Neutral Peak<-current_max, 55.0 vs DB 10.54) [G], P false 'no_reading' reason on under-fetched derived inputs [C], Q seed event stubs [B], R derived-zero consts [A]. Cross-class behavior is consistent, not worse — the defects are pipeline-wide, not class-specific.

## (5) LOG INVENTORY (outputs/logs, session-scoped — dir cleared at 00:43 preflight)
- Files: **27 pipeline_*.jsonl + 27 ai_*.jsonl + 27 response_*.jsonl + 2 failures_*.jsonl = 83** (failures_pytest.jsonl is a harness artifact; failures_r_d7be9457fc.jsonl the only pipeline-fired failures log).
- **Total LLM calls: 198** (cat ai_*.jsonl | wc -l).
- 27 run_ids = 18 sweep + 9 cross. **Every page has BOTH pipeline_ and ai_ logs — ZERO logging gaps.** (The partial matrix above claimed 02-06 logs absent; they are now present — that claim is superseded.)
- prompt -> run_id map: 01 r_f9787f915f (pipeline 23 lines/ai 3) | 02 r_075d05bffb (11/6) | 03 r_99879f110d (15/3) | 04 r_a68ae6e694 (19/8) | 05 r_b57a82feb3 (17/3) | 06 r_aea5abb769 (15/9) | 07 r_82157379cd (14/1) | 08 r_bb525a5212 (16/13) | 09 r_1bc17049b9 (14/5) | 10 r_c7938ef357 (22/20) | 11 r_dd90453138 (20/9) | 12 r_1f97dfa47f (20/9) | 13 r_44796d791a (22/27) | 14 r_d06f6da969 (23/11) | 15 r_f3b19721cb (22/10) | 16 r_8cfd3d6cf1 (17/9) | 17 r_e02e4237bf (14/7) | 18 r_d7be9457fc (15/13) | cross_1 r_ea44a73ed2 | cross_2 r_a280d5c50b | cross_3 r_c1bb1de592 | cross_4 r_b69bd1fbae | cross_5 r_c94382a4f9 | cross_6 r_ab957fb3ac | cross_7 r_102b506a1f | cross_8 r_5caef922fc | cross_9 r_92a2bfb0ae (cross runs: 6 pipeline/3 ai each; cross_9 6/8... per listing 6/3-8).
- TELEMETRY GAP (minor): the failures_ channel fired on only 1 of 42 defect cards — emit/fill defects surface only in pipeline_/ai_/response traces, not failures_.

## (6) BUNDLE
- Bundle path: **/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/outputs/fullsweep_20260706_004334/** (9.8M)
  - logs/ = 83 files (27+27+27+2, copied from outputs/logs)
  - pages/ = 33 files (v18_01..18 + b-variants for the 5 asset-pending re-POSTs 10b/11b/12b/13b/14b/15b + cross_1..9)
  - notes/ copied; host.log (durable stage stream) in place.

## (7) VERDICT — **NOT CERTIFIED**
The contract splits cleanly:
- **CERTIFIED half — plumbing:** (a) routing 18/18 + 9/9 class-correct, zero misroutes, picker safe on every homonym; (b) payload-direct render 70/70 real CMD_V2 components, 0 frames, 0 NaN, 0 whole-card refuse; (c) honest-blank-with-reason machinery works per-LEAF wherever emit chooses it (33 cards, every blank DB-verified honest); infra 0 (5433 open throughout).
- **NOT CERTIFIED — clause (d) ZERO-fabrication is VIOLATED on 42/70 cards.** Strict classification:
  - **DEFECT (42 cards), by blocking layer:** layer2-emit G-family mis-binds 36,39,40,41,42,46*,48,49,51,53,56,57,58,61,62,65,74,75,76,77 + zero-skeletons 19,25 + unbound 79 (*46/44 executed in fill); ems_exec-fill 7,12,13,14,16,18,20,22,44,67; card_payloads/strip seeds 17,36,37,38,51,55,56,59,71; validate/reasons 63; gates bypass systemic (enabler, pages 07/08/11/15/16/17); F timeout 24.
  - **HONEST-GAP (PASS, 33 cards):** all verified against neuract — not blockers.
  - **INFRA:** none.
  - **KNOWN-OPEN [nameplate]:** asset_nameplate still carries 209 class_default fabricated ratings (memory: 20000-vs-160 re-seed pending). It did NOT surface as a defect this sweep (c8 '300 kVA' source=cmd_equipment_table, c40 rated 600 real) — remains open, not a new blocker.
- **Path to certification (fix order per V48 AI-first policy):** (1) close the gates bypass — $ctx-sourced fields and grouped cards MUST pass the same 3 honesty guards (single highest-leverage fix: unblocks pages 07/08/11/15/16/17); (2) emit grounding rule — a slot honest-blanks unless a column of its OWN quantity/unit exists (kills G); (3) re-strip card_payloads.payload_stripped for string-embedded numbers, boolean arrays, tick/event skeletons, axis ticks (kills B: 17,37,38,51,55,56,59,67,71); (4) bind *_event_active registers in fill (kills page-05 A-family); (5) roster energy = pick_mover everywhere (kills 12,13,14,16 false-zeros); (6) seed neuract 3D catalogs from asset_3d_registry (frees 60,63); (7) split/shrink the c24 emit prompt (F). Then re-run this 18+9 sweep for certification.
