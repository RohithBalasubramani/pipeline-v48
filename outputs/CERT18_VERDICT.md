# V48 18-PAGE CERTIFICATION VERDICT

_Generated 2026-07-08 · source: per-page adversarial audits (SSR render + neuract cross-check, per-leaf)_
_Scope: 9 EMS pages + 9 asset-dashboard pages = 18 pages / 70 cards, audited real-or-honest-blank / zero-fabrication / SSR-safe / correct-route._

## 1. CONFIG CERTIFIED

The verdict below was produced against this locked configuration:

- **guided_json: ON** — routing determinism (killed the campaign-long mis-route flakiness)
- **morph-map: OFF** — live A/B regressed; held off
- **prompt-v2: OFF** — live A/B regressed; held off
- **c49 axis-chrome carve-out: ON** — axis/legend chrome exempt from the seed-strip
- **layer2.emit_concurrency = 4** — per-page emit fan-out cap (page-concurrency still ≤2–3 for sweeps)

---

## 2. THE 18-PAGE × CARD TABLE

| nn | page_key | routed_ok | cards ok/total | ssr ok/total | fab | defects (card:layer) | honest_gaps |
|----|----------|-----------|----------------|--------------|-----|----------------------|-------------|
| 01 | panel-overview-shell/real-time-monitoring | yes | 8/8 | 8/8 | 0 | — | 9 |
| 02 | panel-overview-shell/energy-distribution | yes | 2/2 | 2/2 | 0 | — | 5 |
| 03 | panel-overview-shell/energy-power | yes | 4/4 | 4/4 | 0 | — | 6 |
| 04 | panel-overview-shell/harmonics-pq | yes | 5/5 | 5/5 | 0 | — | 6 |
| 05 | panel-overview-shell/voltage-current | yes | **2/5** | 5/5 | 0 | **18:ems_exec-validate, 20:ems_exec-validate, 22:ems_exec-validate** | 2 |
| 06 | individual-feeder-meter-shell/voltage-current | yes | 4/4 | 4/4 | 0 | — | 7 |
| 07 | individual-feeder-meter-shell/real-time-monitoring | yes | **2/3** | 3/3 | **3** | **36:ems_exec-validate (seed→fab)** | 5 |
| 08 | individual-feeder-meter-shell/energy-power | yes | **3/4** | 4/4 | 0 | **39:layer2-emit (false-blank)** | 4 |
| 09 | individual-feeder-meter-shell/power-quality | yes | **2/3** | 3/3 | 0 | **49:layer2-emit (false-blank)** | 8 |
| 10 | diesel-generator-asset-dashboard/voltage-current (pinned dg_1_mfm, asset-picker case) | yes | **3/4** | 4/4 | 0 | **66:layer2-emit (false-blank)** | 3 |
| 11 | diesel-generator-asset-dashboard/engine-cooling (pinned dg_1_mfm, asset-picker case) | yes | **2/3** | 3/3 | 0 | 62:ems_exec-validate (reason-honesty; outage-induced, self-heals — non-blocking) | 3 |
| 12 | diesel-generator-asset-dashboard/fuel-efficiency (pinned dg_1_mfm, asset-picker case) | yes | **2/3** | 3/3 | **1** | **65:ems_exec-fill (fab-by-zero)** | 8 |
| 13 | diesel-generator-asset-dashboard/operations-runtime (pinned dg_1_mfm, asset-picker case) | yes | **2/4** | 4/4 | **3** | **70:layer2-emit (seed→fab), 72:layer2-emit (unit-leak + substitution)** | 6 |
| 14 | transformer-asset-dashboard/tap-rtcc (pinned gic_15_n3_..._transformer_01_se, asset-picker case) | yes | 4/4 | 4/4 | 0 | — | 4 |
| 15 | transformer-asset-dashboard/thermal-life (pinned gic_15_n3_..._transformer_01_se, asset-picker case) | yes | **3/4** | 4/4 | **1** | **77:layer2-emit (fab-const + cross-quantity)** | 5 |
| 16 | ups-asset-dashboard/battery-autonomy (pinned gic_01_n3_ups_01_p1) | yes | **3/4** | 4/4 | 0 | **53:layer2-emit (silent false-blank)** | 3 |
| 17 | ups-asset-dashboard/output-load-capacity (pinned gic_01_n3_ups_01_p1) | yes | 3/3 | 3/3 | 0 | — | 4 |
| 18 | ups-asset-dashboard/source-transfer (pinned gic_01_n3_ups_01_p1) | yes | 3/3 | 3/3 | 0 | — | 3 |

_Pages 10–15 resolved through the AssetPicker single-asset case (pinned meter noted inline); pages 16–18 likewise pin gic_01_n3_ups_01_p1. All 18 routed to the correct target._

---

## 3. TOTALS

| metric | value |
|--------|-------|
| Total cards | **70** |
| cards_ok (real-or-honest-blank, render-correct) | **57 / 70** |
| SSR-clean | **70 / 70** |
| **Fabrication leaves** | **8** (across 5 cards) — required 0 to certify → **NOT met** |
| payload_errors (emit-timeout / truncated) | **0** |
| Misroutes | **0** (18/18 routed_ok) |
| honest_gaps (expected degradation) | ~91 |

Cards not-ok (13): 18, 20, 22 (p05) · 36 (p07) · 39 (p08) · 49 (p09) · 66 (p10) · 62 (p11) · 65 (p12) · 70, 72 (p13) · 77 (p15) · 53 (p16).

---

## 4. DEFECT FAMILIES PRESENT

| family | description | card_ids |
|--------|-------------|----------|
| **A** | fab-by-zero / canned-config-constant shown as live | **65, 77** |
| **B** | seed-leak (unstripped CMD_V2 seed shown as live) | **36, 70** |
| **C** | false-blank (column HAS live data / silently emptied) | **39, 49, 66, 53** |
| D | misroute | — (none; 18/18 routed_ok) |
| **E** | legend/unit leak | **72** (+ 22 latent header mislabel) |
| F | emit-timeout / payload_error | — (none; 0 payload_errors, 70/70 SSR OK) |
| **G** | semantic mis-bind (wrong quantity / substitution) | **72, 77** |
| H | SSR render-crash | — (none; 70/70 SSR-clean) |
| **[+] structural over-blank (order-array)** | anti-fab over-blanked `*Order` presentation arrays → real data renders as an EMPTY component (not in A–H) | **18, 20, 22** |

### Family details

- **A — fab-by-zero / canned constant:**
  - `65` (p12): Efficiency KPI ships **97.0%** = `100 − 3.0` (config `energy_balance.expected_loss_band_pct`) on an all-zero OFF window (`active_power_total_kw` all 0.000); `_has_real_reading` treats 0.0 as a live reading so the dark-feeder honest-blank never fired. SFC/Load correctly blanked the same zero window.
  - `77` (p15): Loss-of-Life scalars (`deltaLolPct`/legend `lol`/`lolAxis` min=max) all false-filled with the const **3.0** via `fn=lossPct → distribution_loss_pct` single-feeder band (also cross-quantity — see G); sibling series `lolPct` honest-blanks the same quantity.
- **B — seed-leak:**
  - `36` (p07): `reactivePowerTrend='Rising'` + `activePowerDeltaPerMinute='+0.0/min'` byte-identical to `card_payloads` default; no trend/rate column exists; contradicts actual falling data (seed-strip missed the `readings` subtree).
  - `70` (p13): `stateKpis control='Auto'` & `breaker='Closed'` leaked from seed as live operational state; `dg_1_mfm` has no control/breaker column (emit classified them as `exact_metadata` instead of blanking).
- **C — false-blank (column has live data):**
  - `39` (p08): `activeEnergyKwh` + `reactiveEnergyKwh` blanked "not measured" though both columns live (sibling card 40 renders them from the same table); emit under-bound the leaves (fn=None/column=None).
  - `49` (p09): pf-angle "Phase angle" blanked "no `phase_angle_deg` column" but the column has 66146/66146 live rows (latest 2.5625° = arccos(0.999)); root = layer1b `col_dict` missing the has-data flag.
  - `66` (p10): 5 voltage leaves (L-L/L-N avg, R-N/Y-N/B-N) blanked "not measured" though each has 108029 non-null rows; sibling card 67 binds+renders the same columns live.
  - `53` (p16): primary `series[0-3].values` silently emptied (accounted nowhere) after emit over-declared `has_data=true` for an uncomputable load-factor proxy (nameplate `rated_capacity_kva` NULL); no per-leaf reason (card 51 honest-blanks the same shape correctly).
- **E — legend/unit leak:**
  - `72` (p13): Active Energy shows 100.2 (real kWh counter delta) under **MWh** unit = **1000× overstatement** (`window_energy_kwh` returns kWh, cell unit MWh, no `/1000`).
  - `22` (p05, latent): headers morphed `voltage→'Sag Events'`, `cause→'Avg Voltage'` over unchanged data-key ids — only surfaces if columnOrder were restored.
- **G — semantic mis-bind / substitution:**
  - `72` (p13): Reactive Energy **3.0 MVARh** = `expectedLossKwh` (3%-of-active) substituted as measured reactive energy; `dg_1_mfm` has no reactive-energy register → fabrication-by-substitution.
  - `77` (p15): distribution-loss-% proxied for insulation loss-of-life (wrong physical quantity).
- **Structural over-blank (order-array) — [not in A–H]:**
  - `18`/`20`/`22` (p05, `ems_exec-validate`): CLASS-4 `unstripped_seed` over-blank drove `tileOrder`/`stackOrder`/`lineOrder`/`columnOrder` to `[]`; `EventsTopStrip`/`EventTimelineChart`/`OtherPanelsTable` build tiles/series/columns via `pres.*Order.flatMap`, so **real payload data (2016/958/1058 stats, 150+ timeline points, 8 real panels) renders as an EMPTY component**. SSR renders (title only) — no crash, but nothing shows. Mirror-image of a seed-leak: it over-blanks structural presentation metadata.

---

## 5. VERDICT

**NOT CERTIFIED.**

The hard bars are not all met: **fabrication = 8 (required 0)**, plus false-blanks that withhold live measured data and a structural over-blank cluster that suppresses real data on render. Passing bars: **SSR 70/70 clean · misroutes 0 · payload_errors 0.**

**Exact blocking defects (12 cards):**

| card | page | family | fix locus (AI → DB → code) |
|------|------|--------|-----------------------------|
| 36 | 07 | B seed-leak → fab | ems_exec-validate — extend seed-strip to `readings.*Trend / *DeltaPerMinute` |
| 65 | 12 | A fab-by-zero | ems_exec-fill — `_has_real_reading` must treat 0.0-on-OFF-window as dark, not live; config-band ≠ measurement |
| 70 | 13 | B seed-leak → fab | layer2-emit — blank `stateKpis control/breaker` (no such column) |
| 72 | 13 | E unit-leak + G substitution | energy.py / layer2-emit — `/1000` for MWh; forbid expectedLoss→reactive substitution |
| 77 | 15 | A const + G cross-quantity | layer2-emit — honest-blank Loss-of-Life; don't proxy distribution-loss |
| 39 | 08 | C false-blank | layer2-emit — bind windowed-energy fn (columns are live) |
| 49 | 09 | C false-blank | layer1b col_dict has-data flag for `phase_angle_deg` → layer2-emit |
| 66 | 10 | C false-blank | layer2-emit — bind live voltage columns like sibling 67 |
| 53 | 16 | C silent false-blank | layer2-emit — don't over-declare has_data; emit per-leaf reason |
| 18 | 05 | structural over-blank | ems_exec-validate — preserve structural `tileOrder`/`segmentOrder` |
| 20 | 05 | structural over-blank | ems_exec-validate — preserve `stackOrder`/`lineOrder` |
| 22 | 05 | structural over-blank + E latent | ems_exec-validate — preserve `columnOrder`; fix header-label morph |

**Certification flips to CERTIFIED once** all fabrication is eliminated (cards 36/65/70/72/77 → honest-blank or corrected unit), the four false-blanks (39/49/66/53) bind their live columns, and the page-05 order-array over-blank (18/20/22) preserves structural presentation metadata so real data renders.

**Non-blocking (does NOT gate cert):**
- `62` (p11): false "not logged" reason text on `loadFactorPct` — the blank VALUE is a defensible standstill-genset honest-blank; `column_logged()` read False only during the run-time :5433 outage and returns True now (self-heals on live re-run). Reason-honesty polish, not a data defect.

---

## 6. EXPECTED HONEST DEGRADATION (not defects)

These pages/cards honest-blank **by physical ground truth** — the pinned electrical meter genuinely lacks the columns for the quantities the card asks for. Verified against `information_schema`/`neuract`; NOT counted as defects (they account for the bulk of the ~91 honest_gaps):

- **UPS battery-autonomy (16, `gic_01_n3_ups_01_p1`):** cards 50/51/52 — no SoC / battery-DC / temperature columns; AC voltage/current are wrong-quantity for battery-side, so binding them would fabricate. (Card 53 is the exception — a real false-blank defect.)
- **UPS source-transfer (18):** cards 54/55/56 — no transfer-readiness / bypass / sync-permissive columns; the event cols present (sag/swell/imbalance) are power-quality, not source transfers. Real input current/voltage series render live.
- **UPS output-load-capacity (17):** card 57 — synthetic /100 score-indices are off-domain for an electrical meter (quantity-vocab honest-blank, refuses load-factor→score); Headroom needs a nameplate (`asset_nameplate` absent in neuract).
- **Transformer tap-rtcc (14, `gic_15_n3_..._transformer_01_se`):** cards 78/80/81 — 0 tap/count/rtcc/oltc columns (71 cols all electrical); tap position genuinely not measured (voltage_avg proxy noted).
- **Transformer thermal-life (15):** cards 74/76 — no temperature/winding/oil/stress columns.
- **DG engine-cooling (11, `dg_1_mfm`):** card 60 (no 3D model configured), card 61 (35-col schema, zero temperature columns).
- **DG fuel-efficiency (12):** card 63 — no fuel columns on the electrical meter (35 cols, none fuel).
- **Panel-overview supply-side (01–05, panel 317 + feeders):** Solar Incomer-1/2 and UPS-05/06 have 0 rows in neuract; transformer feeders `gic_15_n10/n11_..._sch` are absent tables; `rated_capacity_kva` NULL panel-wide → all load/utilization %, denominators, consumed-hints honest-blank. `thd_voltage_*` / `harmonic_5th/7th_pct` all-zero non-null → vThd/h5/h7 honest-blank across the harmonics page.

These confirm the anti-fabrication guard is working as designed on the honest-degradation surface (real-or-honest-blank per leaf) — the certification blockers above are the remaining fabrications, false-blanks, and the order-array over-blank, not this expected degradation.
