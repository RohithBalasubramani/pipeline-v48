# CARD AUDIT MASTER — Fleet-wide fix plan (2026-07-15)

Synthesis of all 16 per-page audits in `docs/card_audit_20260715/`. Every blank leaf
was classified against the **actually-resolved meter** (probed live on neuract :5433),
not against the CMD_V2 demo reference. The doctrine rule is unchanged:

> AI decides open-ended shape · deterministic validates facts + binds/derives ·
> **never fabricate** · honest-blank when the resolved meter truly lacks the register.

The reference implementation of that doctrine already exists as
`ems_exec/executor/canonical_slots.py` (statutory voltage band + legend + avg/max/min
slot fill, adopted for card 37). **Most fixable families below are generalizations of
that same mechanism** — they are noted with **[canonical_slots-family]**.

---

## 1. HEADLINE COUNTS

Counting enumerated **data leaves** (grid-shape roster false-positives and pure
styling/`chrome_noise` excluded — those are not gaps and are called out in §3):

| bucket | ~leaves | ~cards | action |
|---|---|---|---|
| **honest_absent** (resolved meter genuinely lacks the register) | **~230** | 34 | **DO NOT FIX** — data/resolution facts (§3) |
| derivation_gap (inputs present, output not computed) | ~95 | 22 | FIX (derive) |
| binding_gap (column/const exists, slot unbound) | ~40 | 12 | FIX (bind/canonical-fill) |
| mis_bind (bound to wrong table/quantity) | ~11 | 3 | FIX (rebind) |
| windowing (roster/bucket fan-out incomplete) | ~15 | 4 | FIX (complete roll-up) |
| **total fixable data leaves** | **~150** | **~30 card-instances (23 distinct cards)** | |
| chrome_noise / grid_shape (excluded above) | ~900+ | — | not gaps |

**Bottom line: the honest_absent majority is correct.** Roughly 60% of enumerated
blank leaves are structurally not on the resolved meter. The remaining ~150 are
fixable with **zero fabrication** — every one either binds an existing column,
derives from an already-present series, completes a member roll-up, or fills a known
policy/statutory/frame constant.

---

## 2. FIX-FAMILIES (ranked by # cards affected, then # leaves)

### F1 · `canonical_threshold_fill` — **9 cards, ~22 leaves** **[canonical_slots-family]**
- **Mechanism:** slots that carry a **known policy / statutory / frame constant**, not
  meter data, are emitted UNBOUND and blank. The executor already owns the fill point
  (`canonical_slots.py`); its vocabulary just doesn't include these constants yet.
- **Cards / leaves:**
  - 48 Distortion — `i-thd.maxLine/minLine`, `v-thd.maxLine/minLine` (IEEE-519 THD limits, 4)
  - 49 Load Impact — `pf-angle.watchLines[0]` (lag-watch limit), `pf-health.stats[3]` + `pf-health.watchLines[0]` (PF target 0.95, 3)
  - 24 Harmonics Timeline — `timeline.limits.{iThdLimit,vThdLimit,truePfFloor,truePfTarget,neutralLimitA}` (5)
  - 51 Battery History — `thresholds[0]/[1]` (ready 60 / moderate 30, 2)
  - 52 Backup Readiness — `readyMarkerPct` (60, 1)
  - 53 Backup History — `thresholds[0]/[1]` (60/30, 2)
  - 54 Transfer readiness — `scoreMax` (100), `readyMarkerPct` (60) (2)
  - 55 Activity — `windowDays` (30), `tickStartLabel` (−30d) (2)
  - 56 Source Transfer Composite — `floor.value` (watchpoint 70, 1)
- **Root cause:** canonical_slots vocabulary covers voltage band only; IEEE-519 THD
  limits, regulatory PF target (0.95), gauge max/marker (100/60), ready/moderate zone
  markers (60/30), window/axis frame constants (30, −30d) and watchpoints (70) are all
  legitimate deterministic constants with no slot filler.
- **Doctrine fix:** extend `canonical_slots.py` with a policy-constant table keyed by
  slot semantic (`ieee519_v_thd_limit`, `pf_regulatory_target`, `gauge_max`,
  `ready_marker`, `moderate_marker`, `window_days`, `watchpoint`). Deterministic,
  fact-typed (a standard, not a measurement), never touches meter data. This is the
  single **lowest-risk, highest-card-count** lever in the whole fleet.

### F2 · `panel_aggregate_rollup_completion` — **4 cards, ~24 leaves** (structural)
- **Mechanism:** panel-aggregate cards whose member fan-out either binds the wrong
  table, emits a zero-skeleton, or stops after one bucket — while sibling cards on the
  same page prove the roll-up works.
- **Cards / leaves:**
  - 15 Today live power (energy-power) — `value/metrics[0,1]/segments[0,1]/insight`
    bound `source=live` **to the panel control table** `pcc_panel_1_feedbacks` (no power
    columns). **mis_bind** → rebind to Σ-member roll-up exactly as siblings 14/16/17 do (6).
  - 19 AI Summary (voltage-current) — `summary.stats.{sag,swell,total,current,neutral}`,
    `worstCurrent/worstVoltage/selectedPanel` emitted as `_zero_skeleton` instead of the
    member fan-out cards 20/22 already run (~8).
  - 13 Energy Flow — `kpis.feederOutputKwh`, `allTotalKw/allTotalKwh`: consumer kWh
    exists (169,428 = Σ member `totalKwh`) and the kW sibling was filled; the kWh rollup
    slot was simply not populated (3).
  - 16 Consumption Trend — daily trend collapsed to 1 bucket though member data spans 8
    days; energy-delta daily roll-up must emit all buckets (`windowing`, ~7).
- **Root cause:** roll-up is per-slot, not per-card — a card can have some member-folded
  slots filled and others left on the raw asset table or on a single bucket.
- **Doctrine fix:** make the panel-aggregate resolver the **default source for every
  power/energy slot on a panel-scoped card** (not just the ones the emit happened to
  wire). Validate against the sibling card that already rolls up. Card 15 is the one
  true mis-bind; the rest are unfinished fan-outs.

### F3 · `loadfactor_derivation` — **4 cards, ~6 leaves**
- **Mechanism:** load-factor / peak-load-% computed from an **avg÷peak ratio** of a
  present power series — needs **no nameplate rating** (distinct from the
  rating-nulled honest cases in §3).
- **Cards / leaves:** 15 `metrics[2]` (1) · 17 `stats[1]` + `insight` (2) · 62
  `kpis[0]` peak-load% + `legend[2]` load (2) · 64 `avgLoad` (1).
- **Root cause:** `loadFactorPct` fn is proven on these meters (e.g. card 65 Load 56.7,
  card 71 avg-load) but not routed into these sibling slots; some were mis-declared to a
  raw-kW proxy that a unit-crossing gate correctly blocked.
- **Doctrine fix:** route these slots through the existing `loadFactorPct(avg,peak)` fn.
  Deterministic, fact-validated (power series present), no rating dependency.

### F4 · `phase_delta_derivation` — **4 cards, ~20 leaves**
- **Mechanism:** per-phase tile `delta`/`deltaText` renders "—" while the phase `value`
  renders. Voltage delta = `voltage_r/y/b_deviation_pct` (present); current delta =
  (phase − avg)/avg from present phase currents (deviation cols all-NULL).
- **Cards / leaves:** 43 voltage phases[0..2] (6) · 45 current phases[0..3] (8) ·
  66 (DG) phases delta · 68 (DG) phases delta.
- **Root cause:** phase-tile geometry treated as chrome; the delta text is real
  derivable data.
- **Doctrine fix:** deterministic per-phase delta at fill time — deviation column when
  present, else (phase−mean)/mean. Bar-position pcts (`tail/width/markerPct`) additionally
  need the nominal band and belong to F6 (voltage) or are honest (current, no rating).

### F5 · `series_summary_derivation` — **4 cards, ~11 leaves**
- **Mechanism:** a scalar `legendValue` / `averageStat` / `caption` reduces an
  **already-bound series** to one number, but the reduction wasn't run.
- **Cards / leaves:** 48 `i-thd/v-thd.averageStat` (avg over bound THD series, 2) ·
  51 `series[0..3].legendValue` (4) · 53 `series[0..3].legendValue` (4) ·
  45 `summary.caption` (avg + peak=`current_max`, 1).
- **Root cause:** legend/caption slots emitted UNBOUND; the series they summarize is
  already in the payload.
- **Doctrine fix:** deterministic post-reduce (avg/last/peak) of the sibling bound
  series into its own legend/caption slot. No fetch, no fabrication.

### F6 · `nominal_band_derivation` — **3 cards, ~7 leaves (+9 dependent geometry)** **[canonical_slots-family]**
- **Mechanism:** shaded/expected voltage band + band-relative marker positions derived
  from **nameplate nominal** (nameplate-first) ± statutory %.
- **Cards / leaves:** 43 `band.markerPct` + phasebar geometry (needs band) · 44
  `expectedMax/expectedMin` (2) · 67 (DG) `maxLine/minLine/expectedMax/expectedMin` ±5% band (4).
- **Root cause:** same driver as the adopted card-37 fix — but these sibling cards
  weren't wired to the nominal-band filler; the HT feeder additionally carries a **wrong
  415 V nominal**, so the band must use the true 6351 V / 11 kV nameplate.
- **Doctrine fix:** reuse the `canonical_slots` + `derivation.nameplate_nominal_first`
  path already ADOPTED on card 37, extended to expected-band and phasebar-geometry
  slots. Fix the HT nominal first (nameplate-first) or the band will be nonsense.

### F7 · `aggregate_from_components` — **3 cards, 5 leaves**
- **Mechanism:** the **bound** aggregate column (`current_avg`, `current_unbalance_pct`)
  is **100% NULL** on the HT feeder, but the component phase columns
  (`current_r/y/b`) are fully present. This is NOT a frame rescue — derive the aggregate.
- **Cards / leaves:** 38 `metrics[2]` Average (1) · 45 `metrics[0]` unbalance +
  `summary.value` avg (2) · 46 `stats[1]` avg + `stats[2]` unbalance (2).
- **Root cause:** the meter never materialized the avg/unbalance registers; the emit
  bound them anyway and got a null column.
- **Doctrine fix:** at fill time, when a declared aggregate column is all-NULL but its
  components are present, derive `mean(phases)` / `(max−min)/mean·100`. Fact-gated on
  component presence; falls back to honest-blank if components also absent.

### F8 · `last_nonnull_windowed_agg` — **3 cards, 3 leaves**
- **Mechanism:** column is fully/sparsely populated but `agg=last` lands on the
  **DG-off zero/null tail** (DG-1 currently OFF: latest row 0 V/0 A/dev −100%).
- **Cards / leaves:** 66 `metrics[0]` (voltage_ln_unbalance) · 67 `stats[1]` (worst
  spread) · 68 `metrics[1]` (current_unbalance). Sibling card 69 already recovered 2.33
  via windowed max-agg — proof this is an agg-choice bug, not absence.
- **Root cause:** snapshot cards use `agg=last`, which is null on an idle asset.
- **Doctrine fix:** last-non-null / windowed agg for snapshot slots on
  intermittently-off assets. Verify against card 69's recovered values.

### F9 · `frame_declared_rescue` — **1 card, 5 leaves**
- **Mechanism:** columns FULLY populated but emitted `source=frame` (honest-blanked);
  rebind `source=live` (+ V→kV morph for the kV slot).
- **Cards / leaves:** 66 (DG) `phases[0..2].value` (voltage_ry/yb/br), `metrics[1]`
  (voltage_ln_avg), `summary.value` (voltage_ll_avg → needs V→kV scaling).
- **Root cause:** classic frame-declared-bindable rescue; the unit-crossing gate blocked
  the kV slot even though the V column is present.
- **Doctrine fix:** rebind to the declared column with a whitelisted unit morph
  (V→kV) when column present. High-value on DG voltage page.

### F10 · `event_markers_unbound` — **1 card, ~14 leaves**
- **Mechanism:** sag/swell event markers + counts are null though
  `sag_event_active`/`swell_event_active` are data-bearing 0/1 flags.
- **Cards / leaves:** 44 `events[0..11].index` (12) + `legend[0..1].value` (2).
- **Root cause:** emit declared no event slots; the rising-edge counter already used on
  panel cards 20/22 isn't applied here.
- **Doctrine fix:** bind event markers to sag/swell rising edges (reuse the panel
  rising-edge counter). **Pair with F6** — on the HT feeder the wrong 415 V nominal makes
  "swell" fire almost always; counts are real but meaningless until the nominal band is
  corrected.

### F11 · `unbound_electrical_bind` — **2 cards, 4 leaves** (role-gated)
- **Mechanism:** an unbound slot maps to a present electrical column.
- **Cards / leaves:** 50 Battery Health `metrics[1]`→`voltage_avg`, `metrics[2]`→`current_avg`
  (output V/I) · 56 Source Transfer `inputVoltageV`→`voltage_ll_avg`, `inputCurrentA`→`current_avg`.
- **Root cause:** slots left unbound though the column exists with data.
- **Doctrine fix:** bind — **but role-gate it.** Source-transfer input V/I is a clean
  bind. Battery "output V/I" onto a UPS electrical MFM is defensible but must not be
  relabeled as battery-domain; and do NOT bind a `bypass*` slot to the meter's own
  `frequency_hz` (that mislabels the source — kept honest_absent in §3).

### F12 · `energy_register_bind_and_power_integration` — **2 cards, 5 leaves**
- **Mechanism:** energy slots derivable from present registers/power series.
- **Cards / leaves:** 64 `totalKwh` ← windowed max−min of `active_energy_import_kwh` (1) ·
  72 `apparentMvah` (a **null-bug**: twin cell already computed 29.94 with the same fn) +
  `reactiveMvarh` (mis-bound to `loadFactorPct`; correct = ∫`reactive_power_total_kvar` dt)
  + `activeFraction`/`reactiveFraction` (unblock once reactiveMvarh derived) (4).
- **Doctrine fix:** fix the fill-order/target-column collision on `apparentMvah`; add a
  power-integration fn for reactive/apparent **energy** from the kVAR/kVA power series.

### F13 · `narrative_from_present_data` — **3 cards, ~5 leaves** (low priority)
- **Mechanism:** insight/summary text where the underlying series **is present**.
- **Cards / leaves:** 43 `insight`, 44 `insight` (templatable from present spread/event
  series) · 7 (panel rail) `aiSummaryText` (reuse the card-8 summary already generated
  this run).
- **Doctrine fix:** template narrative from present series (AI-open text, deterministic
  inputs); wire the rail to reuse the sibling AI summary. Only where inputs exist — most
  other insights are honest_absent (§3) because their inputs are absent.

### Singletons (fix opportunistically inside the nearest family)
- 64 `runHours` — new fn: count intervals where `active_power>0` × interval_seconds (inputs present, no catalog fn today).
- 47 `trendPctPerHour` — THD %/hr trend (needs a 2nd fetch; low value, ref is a demo artifact).
- 21 `panels[*].table` — roster node identifier (cosmetic; cards 20/22 fill it).
- 66 `Spread` — `voltage_ln_max − voltage_ln_min` (both full).
- 49 `pf-health.stats[2]` PF-Gap — from `kpi_displacement_pf` + `power_factor_total` (both present).

---

## 3. HONEST-ABSENT SUMMARY — resolution/data facts, **NOT fixable code**

These EMS-vs-V48 differences exist because V48's **resolved meter genuinely lacks the
register**. They are correct blanks; "fixing" them would fabricate.

1. **Reactive-energy register on the HT transformer** (card 36). `reactive_energy_import_kvarh`
   is all-NULL on `gic_15_n3_pcc_01_transformer_01_se`; `apparent_energy_kvah` is present but
   a **different quantity** (apparent ≠ reactive). HT transformer meters log active+apparent
   energy, not a reactive-energy register.
2. **HT-vs-LV resolution.** The feeder meter is an **11 kV HT transformer meter** (~6351 V L-N).
   Any 415 V-flavored demo band/expected-band is wrong. `current_avg`, `current_unbalance_pct`,
   `current_r/y/b_deviation_pct` **columns exist but are all-NULL** (HT CT wiring) — hence F7
   derives them from phases rather than binding the dead register. **No 415 V transformer meter
   exists in V48** — the LV view is a genuine data gap, not a resolver bug.
3. **No nameplate / rating anywhere.** `lt_mfm.rated_capacity_kva` is NULL for DG-1 and the PCC
   panels; no `asset_nameplate` table. → every load-%-of-rated, demand-limit, headroom,
   utilization, UPS-capacity, CT/breaker current-limit and "contracted/critical" threshold is
   honest_absent (`loadfactor_rating_nulled`, `current_threshold_nameplate_absent`,
   `nameplate_rating_absent`). Cards 57/58/59 (UPS capacity), 70/71 (DG duty), 12/13/14/15/17
   (panel targets) all trace here. Would only light up if a nameplate/contract figure were seeded.
4. **Battery domain absent** (cards 50, 52). SOC, battery temperature, runtime-minutes, backup
   readiness — the UPS resolves to an **electrical MFM**; there is no BMS column.
5. **Bypass / transfer / readiness domain absent** (cards 54, 55, 56, 59). A single meter measures
   one source: no separate bypass-line voltage, no transfer-event log, no readiness composite.
   `frequency_hz` exists but is **this meter's own frequency** — attributing it to the bypass
   *source* would mislabel the role, so it stays blank.
6. **Engine / thermal / fuel / oil / RPM domain absent** (cards 60, 61, 62, 63, 65). `dg_1_mfm` is
   an electrical MFM: no coolant/exhaust/oil temperature, oil-pressure, engine-speed, or
   fuel level/flow/temperature sensors. All thermal/fuel/pressure/speed leaves are structural.
7. **Runtime / service / reliability counters absent** (cards 70, 71, 72). No run-hours, start
   counts, availability/uptime, MTBF/MTTR, or service-interval — these come from a genset
   controller / service contract, not an MFM.
8. **Voltage-THD & individual harmonic orders, flicker, crest, K-factor** (cards 47, 48, 49;
   panel 23–27). Meters log **current**-THD + PF + neutral only. `thd_voltage_*`,
   `harmonic_5th_pct`, `harmonic_7th_pct` columns **exist but are all-NULL** on every member;
   3rd-order / peak-THD / K-factor / flicker / crest have **no column**. Genuine logging gap.
9. **Empty member tables** (panel pages). Solar-Incomer-1/2, UPS-05, UPS-06 meter tables have
   **0 rows all-time** → honest per-member absence in every roster card.
10. **Source/incomer meters absent** (card 13). The incomer side (solar + PCC-transformer feeders)
    is empty or the table doesn't exist → loss/efficiency/source-input/supplied are honest.
11. **HHF is an APFC capacitor bank, not a load feeder** (cards 16, 17, 7, 9). Physical HHF feeders
    read ~0 kW / −15.9 kVAr (capacitive) — no analog to the demo's HHF consumption line.
12. **SEC (kWh/tonne)** (card 14) needs production tonnage — no such signal on any meter.
13. **Rate-change (V/min, A/min)** (cards 43, 45) — a time-derivative not in the snapshot schema.
14. **Grid-shape (NOT gaps).** ~900 of the raw candidate records are **6 live members vs 10
    hard-coded demo feeders** (`panels[6..9]`, `MFM_0xx` ids) or pure chrome (opacity, line
    width/dash, selection state, axis ticks). Excluded from all fixable counts.

---

## 4. RECOMMENDED IMPLEMENTATION ORDER (highest card-impact × lowest risk first)

Every step is **flag-gated OFF (byte-identical), verified against the live/sibling
that already renders, then adopted**.

| # | Family | Cards | Risk | Why here | Flag (suggested) |
|---|---|---|---|---|---|
| **1** | **F1 canonical_threshold_fill** | 9 | very low | pure extension of adopted `canonical_slots.py`; constants are standards, not meter data → 0 fabrication | `fill.canonical_slots.policy_consts` |
| **2** | F6 nominal_band_derivation | 3 | low | reuses adopted card-37 nameplate-nominal path; **fix HT nominal first** | `derivation.nameplate_nominal_first` (extend) |
| **3** | F7 aggregate_from_components | 3 | low | deterministic, fact-gated on component presence; recovers HT current avg/unbalance | `fill.derive_aggregate_from_phases` |
| **4** | F9 frame_rescue + F8 last_nonnull_agg | 3 (DG 66/67/68) | low-med | rebind FULL columns + windowed agg; verify vs card 69's live values | `bind.frame_declared_rescue`, `agg.last_nonnull` |
| **5** | **F2 panel_aggregate_rollup** | 4 | med (highest leaf-impact) | biggest structural win; card 15 mis_bind + 19/13/16 fan-out; verify vs siblings 14/16/17/20/22 | `panel.rollup_all_power_slots` |
| **6** | F3 loadfactor_derivation | 4 | low-med | route present power through proven `loadFactorPct`; no rating needed | `derive.load_factor_no_rating` |
| **7** | F4 phase_delta + F5 series_summary | ~6 | low | reduce/derive from already-present series & deviation cols; mostly cosmetic-safe | `fill.phase_delta`, `fill.series_summary` |
| **8** | F10 event_markers_unbound | 1 | med | reuse rising-edge counter; **gate on F6** (nominal band) or swell count is meaningless | `bind.sag_swell_markers` |
| **9** | F11 unbound_electrical_bind | 2 | med (role-gated) | bind present columns; block bypass←own-frequency mislabel | `bind.unbound_electrical` |
| **10** | F12 energy/power_integration | 2 | med | fix `apparentMvah` null-bug (verify twin) + reactive/apparent-energy integration fn | `derive.power_integration_energy` |
| **11** | F13 narrative + singletons | 3+ | low | templated text where inputs present; new `runHours` fn; THD-trend | `fill.narrative_from_series` |

**Rationale:** steps 1–4 all **generalize the already-adopted `canonical_slots.py` /
nameplate-nominal / frame-rescue mechanisms** — highest confidence, touch the most
cards, add no new binding path. Step 5 is the largest single leaf-impact but changes
the panel binding path, so it goes after the safe deterministic wins and is verified
against the three sibling cards that already roll members up. Everything after 5 is
narrower and rides on top.
