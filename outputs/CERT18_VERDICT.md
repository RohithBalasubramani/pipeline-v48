# V48 18-PAGE CERTIFICATION VERDICT

**Run date:** 2026-07-07 · **Scope:** 9 EMS pages + 9 asset pages (18 leaf routes) · **Rule:** every card renders real-or-honest-blank per leaf, zero fabrication.

---

## 1. CONFIG CERTIFIED

The verdict below is bound to this exact pipeline configuration:

| Knob | State | Reason |
|---|---|---|
| `guided_json` | **ON** | structured emit |
| morph-map | **OFF** | live A/B regressed |
| prompt-v2 | **OFF** | live A/B regressed |
| c49 axis-chrome carve-out | **ON** | axis/legend chrome exempted from data-leaf gate |
| `layer2.emit_concurrency` | **4** | parallel per-card emit |

---

## 2. THE 18-PAGE × CARD TABLE

| nn | page_key | routed_ok | cards ok/total | ssr ok/total | fabrication | defects (card:layer) | honest_gaps |
|----|----------|:---------:|:--------------:|:------------:|:-----------:|----------------------|:-----------:|
| 01 | panel-overview-shell/real-time-monitoring | ✅ | 8/8 | 8/8 | 0 | — | 7 |
| 02 | panel-overview-shell/energy-distribution | ✅ | 2/2 | 2/2 | 0 | — | 8 |
| 03 | panel-overview-shell/energy-power | ✅ | 4/4 | 4/4 | 0 | — | 4 |
| 04 | panel-overview-shell/harmonics-pq | ✅ | 5/5 | 5/5 | 0 | — | 8 |
| 05 | panel-overview-shell/voltage-current | ✅ | 4/5 | 5/5 | 0 | 18:ems_exec-fill (false-blank) | 8 |
| 06 | individual-feeder-meter-shell/voltage-current | ✅ | 4/4 | 4/4 | 0 | — | 7 |
| 07 | individual-feeder-meter-shell/real-time-monitoring | ✅ | 3/3 | 3/3 | 0 | — | 3 |
| 08 | individual-feeder-meter-shell/energy-power | ✅ | 4/4 | 4/4 | 0 | — | 6 |
| 09 | individual-feeder-meter-shell/power-quality | ✅ | 3/3 | 3/3 | 0 | — | 7 |
| 10 | diesel-generator-asset-dashboard/voltage-current (pinned asset_id=2, asset-picker case) | ✅ | 4/4 | 4/4 | 0 | — | 6 |
| 11 | diesel-generator-asset-dashboard/engine-cooling (pinned asset_id=2, asset-picker case) | ✅ | 3/3 | 3/3 | 0 | — | 4 |
| 12 | diesel-generator-asset-dashboard/fuel-efficiency (pinned asset_id=2, asset-picker case) | ✅ | 3/3 | 3/3 | 0 | — | 7 |
| 13 | diesel-generator-asset-dashboard/operations-runtime (pinned asset_id=2, asset-picker case) | ✅ | 2/4 | 4/4 | **2** | 72:ems_exec-fill (fab-by-mislabel), 73:ems_exec-fill (false-blank) | 5 |
| 14 | transformer-asset-dashboard/tap-rtcc (pinned transformer, asset-picker case) | ✅ | 4/4 | 4/4 | 0 | — | 4 |
| 15 | transformer-asset-dashboard/thermal-life (pinned transformer, asset-picker case) | ✅ | 4/4 | 4/4 | 0 | — | 7 |
| 16 | ups-asset-dashboard/battery-autonomy (pinned UPS, asset-picker case) | ✅ | 4/4 | 4/4 | 0 | — | 4 |
| 17 | ups-asset-dashboard/output-load-capacity (pinned UPS, asset-picker case) | ✅ | 2/3 | 3/3 | **2** | 59:layer2-emit (misbind fab ×2) | 3 |
| 18 | ups-asset-dashboard/source-transfer (pinned UPS, asset-picker case) | ✅ | 3/3 | 3/3 | 0 | — | 4 |

---

## 3. TOTALS

| Metric | Value | Cert threshold |
|---|---|---|
| Total cards | **70** | — |
| cards_ok | **66 / 70** | — |
| SSR-clean | **70 / 70** | must = total |
| **Fabrication instances** | **4** (on pages 13, 17) | **MUST be 0 → FAIL** |
| Payload errors | 0 | must = 0 |
| Misroutes | 0 (18/18 routed_ok) | must = 0 |
| Honest gaps (per-leaf telemetry) | 102 | informational |

---

## 4. DEFECT FAMILIES PRESENT

| Fam | Description | Card_ids | Present |
|-----|-------------|----------|:-------:|
| A | fab-by-zero (0/rated shown as %) | — | none |
| B | seed-leak (Storybook const shipped as reading) | — | none (all seeds honest-blanked: cards 8, 37, 38, 44, 47, 61, 62, 64, 65, 74, 75, 78–81, 51–54, 57) |
| C | false-blank (column has live data) | **18** (worst-chip vAvg/vMax/vMin, cols exist with 2929/3566 live rows), **73** (4 power-trend series, 79587 live rows, maxY=104.9 proves frame had data) | **2 cards** |
| D | misroute | — | none (18/18 routed_ok) |
| E | legend/unit leak | — | none |
| F | emit-timeout | — | none |
| G | semantic mis-bind (wrong column shown as another quantity) | **72** (windowEnergyKwh hardwired to `active_energy_import_kwh` → active delta 100.2 rendered as Reactive Energy MVARh; real reactive ≈16.7 kVArh), **59** (bypassVoltageV←`voltage_avg` + bypassFrequencyHz←`frequency_hz` present input/line values as bypass readings on a meter with no bypass sensing; also 'Time' label mis-bound to raw `active_power_total_kw`) | **2 cards** |
| H | SSR render-crash | — | none (70/70 rendered OK) |

**Blocking families:** C (false-blank of measurable data) and G (semantic mis-bind fabrication).

---

## 5. VERDICT

> ## ⛔ NOT-CERTIFIED
>
> **Blocked on 4 fabrication instances across 4 cards / 2 asset pages** (fabrication MUST be 0). SSR is fully clean (70/70), routing is fully clean (18/18), and no seed-leak/emit-timeout/render-crash defects exist — but the two mis-bind fabrications and two false-blanks fail the real-or-honest-blank contract.

### Exact blocking defects (must-fix to certify)

1. **Card 72 (page 13, operations-runtime) — Family G fab-by-mislabel.**
   `windowEnergyKwh` is hardwired in `registry.py:59` to `['active_energy_import_kwh']`; `energy.py window_energy_kwh()` reads only that register, so the **active** 24h delta (≈100.2) is rendered into the **reactive** slot (`reactiveMvarh` = 100.2 MVARh + `cells[1] "Reactive Energy"` = 100.2). Real reactive 24h ≈16.7 kVArh; no reactive-energy register exists in `dg_1_mfm`. Correct fn `reactiveEnergyMvarh` exists but is unused. **Honest outcome should have been blank.**

2. **Card 73 (page 13, operations-runtime) — Family C false-blank.**
   All 4 bucketed power-trend series (`active_power_total_kw` / `reactive_power_total_kvar` / `apparent_power_total_kva` / `power_factor_total`) render `values=[]` with verdict honest_blank/none, yet the neuract this-week window has **79587 live rows** (active max 863.95 kW) and `maxY=104.9` **did** compute from that same frame — proving the frame carried live data. Series were silently dropped with **no gap reason** → whole-card false-blank of fully measurable data. Layer: `ems_exec-fill`.

3. **Card 59 (page 17, output-load-capacity) — Family G semantic mis-bind ×2.**
   `data_instructions.fields` binds `bypassVoltageV → voltage_avg` (same col as `inputVoltageV`) and `bypassFrequencyHz → frequency_hz`, so **input voltage / line frequency are presented AS bypass readings** for all 154 points — directly contradicting the card's own `data_note` ("Bypass Voltage … honest-blanks, not measured by this meter"). The meter has no bypass column. Secondary: `composite.points[*].label` ('Time') is mis-bound to raw `active_power_total_kw`, rendering negative kW (~-190) as x-axis time labels (`CompositeChartCard.tsx:348`). Layer: `layer2-emit`.

### What must go green

- Card 72: route `reactiveMvarh`/`cells[1]` to `reactiveEnergyMvarh` (or honest-blank — no reactive register in `dg_1_mfm`).
- Card 73: unblock the 4 trend series from the frame that already computed `maxY`, or emit an explicit gap reason (it is measurable, so it must render).
- Card 59: honest-blank `bypassVoltageV`/`bypassFrequencyHz` (no bypass sensing on this UPS meter); re-bind the 'Time' label slot to the timestamp, not `active_power_total_kw`.

---

## 6. EXPECTED HONEST DEGRADATION (not defects)

These pages are honest-blank-heavy **by design** — the pinned meter genuinely lacks the queried columns. All were verified against `information_schema` / neuract non-null counts and carry per-leaf reasons; they are correct honest degradation, **not** defects:

- **Page 16 — ups-asset-dashboard/battery-autonomy** (cards 50–53): SOC/DC-bus/thermal/autonomy-index score families and battery Temperature have **no columns** on the electrical MFM `gic_01_n3_ups_01_p1` (0 `%temp%` / `%autonom%` / score matches). All seeds stripped; series honest-empty.
- **Page 18 — ups-asset-dashboard/source-transfer** (cards 54–56): no readiness/input/bypass/sync-score column and no transfer-count column in the 72-col table; readiness + transfer-count leaves honest-blank. Real V/A/Hz series (238.5 V / 50.0 Hz / 263.3 A) render.
- **Page 11 — dg/engine-cooling** (cards 61, 62): coolant/oil/intake/exhaust temperature and load%/oil-pressure columns do not exist in the 35-col electrical `dg_1_mfm`; unit-mismatch honest-blank, no power number shown as a temperature.
- **Page 12 — dg/fuel-efficiency** (cards 63–65): no fuel-family / SFC / nameplate columns; fuel legends, SFC ratio (no production_base_units), and `avgLoad` (no `asset_nameplate`) honest-degrade.
- **Page 15 — transformer/thermal-life** (cards 74–77): no temperature / lifetime / aging-factor columns on the 70-col electrical transformer MFM; design-life (25 yr) and derated-kVA (2500) seeds correctly blanked.
- **Page 14 — transformer/tap-rtcc** (cards 80, 81): 0 tap/count/setpoint/rtcc columns on the asset table; tap-activity leaves honest-blank.
- **Page 10 — dg/voltage-current** (cards 66–69): DG is genuinely **off/idle** — voltage/current 0.0 and `-100%` deviation are REAL readings (142/79554 non-null), not blanks.

Note also the recurring, verified honest gaps across EMS panel pages 01–05: **PCC-Panel-1 has no `asset_nameplate.rated_kva`**, so all contracted-capacity / utilization% / load% leaves honest-blank; and the **dark feeders** (UPS-05/06 = 0 rows, Solar Incomers = 0 rows, Transformer members = tables that do not exist) honest-blank their slots. These are data-availability facts, not pipeline defects.

---

## 7. DEFECT FIXES (2026-07-07, post-verdict)

All 4 blocking defects fixed AI/gate/code-first, generic (no card ids), DB-driven where applicable. pytest: 577 non-DB pass; the only failures are the `:5433` neuract tunnel outage (Connection refused), not regressions.

| Defect | Fix | Verification |
|---|---|---|
| **c72** reactive-reads-active (Fam G) | `verify._polarity_conflict` energy-polarity guard driven by the registry `_QUANTITY` table — an active-energy fn bound to a reactive (MVARh) slot is refused → reactive **honest-blanks** (dg_1_mfm has no reactive register) with a `quantity_mismatch` reason | LIVE (DB up): reactive=None, active=100.2 real; +tests |
| **c59** bypass←input (Fam G ×2) | new **source-role wall** `quantity.source_roles` (bypass=dedicated, input=non-dedicated): a dedicated-sensing slot binds only a same-role source → `bypassVoltageV←voltage_avg` honest-blanks, `inputVoltageV←voltage_avg` stays valid; + `quantity.time_axis_label_tokens` (Time label ← power column honest-blanks) | LIVE (DB up): bypass=None, real time labels; +tests |
| **c73** power-trend false-blank (Fam C) | **3 root causes**: (a) fill.py solo-bucket→wildcard array-grow (direct path); (b) `column_override` `$ctx→live` on a standalone card naming a real column; (c) **ROOT**: `is_group_card` now requires a real `shared_ctx_ref` — a mere `time-bucket` date-sync coupling no longer makes a card a shared-context `$ctx` group (Approach-B deferred → standalone per-card fill, the plan's path) | OFFLINE + unit tests (7/7). **LIVE data-fill re-cert PENDING the :5433 tunnel return** |

**Adopted config unchanged:** guided_json ON, morph-map OFF, prompt-v2 OFF, c49 carve-out ON, emit_concurrency=4, + the new source-role / time-axis / energy-polarity / is_group_card fixes.

**Remaining to close cert:** with `:5433` restored, re-fire pages 13 + 17 and re-audit cards 72/73/59 — c72/c59 already proved clean live; c73 needs the live data-fill confirmation (fields now bind `src=live`; the neuract power trend should render). Expected result: **70/70 CERTIFIED**.
