# Card audit — individual-feeder-meter-shell/real-time-monitoring

- **Page key**: `individual-feeder-meter-shell/real-time-monitoring`
- **Meter table**: `gic_15_n3_pcc_01_transformer_01_se` (HT transformer feeder meter, GIC-15-N3-PCC-01)
- **Cards on page**: 36 Power & Energy, 37 Voltage Monitor, 38 Current Monitor
- No grid cards (5/24) on this page.

## Meter probe (7-day non-null counts)

| column | non-null rows | note |
|---|---|---|
| reactive_energy_import_kvarh | 0 | all-null on this meter |
| reactive_energy_export_kvarh | 0 | all-null |
| apparent_energy_kvah | 49021 | present — but a DIFFERENT quantity (apparent, not reactive) |
| current_avg | 0 | all-null |
| current_max | 49021 | present |
| current_min | 49021 | present |
| current_neutral | 49021 | present |
| current_r / current_y / current_b | 49021 each | present |

- No `asset_nameplate` table exists in neuract; the meter has no `rated*/rating/ct_*/ampac*` column → no current-limit source.

---

## Card 36 — Power & Energy (Real-Time)

Filled leaves are healthy: activePower (758.3 kW), activeEnergy (20483 kWh, windowed), apparentPower (761.3 kVA), reactivePower (57.0 kVAR), projectedDemand (943, derived worstPeakKw), both dataSeries + all time axes.

### Blank data leaves

- **`.readings.reactiveEnergy.value` / `.displayValue`** — ref 4562 kVARh, v48 `—`.
  - Natural column = `reactive_energy_import_kvarh` → **0 non-null (all-null on this meter)**.
  - The di bound `metric=apparent_energy_kvah, source=frame` into this kVARh slot. `apparent_energy_kvah` DOES have data, but it is a different quantity (apparent kVAh ≠ reactive kVARh). The pipeline `_normalized` note shows it correctly **blocked the unit-crossing proxy** and honest-blanked.
  - **Verdict: honest_absent.** Binding apparent→reactive would fabricate wrong-quantity data. The true reactive-energy register is empty on this HT meter. `fix_family = reactive_energy_absent`.

---

## Card 37 — Voltage Monitor (Real-Time)

No blank data leaves in the render. All three phase series, metrics (Average/Max/Min), legend R/Y/B, and both thresholds are filled. Thresholds render as `Max - 6985.9V`/`Min - 5715.8V` — the `_honest_blanked` note shows the original demo consts 420/400 were dropped and the **canonical voltage band (statutory) fill** supplied the ±band. Canonical-slot fill is working here; no gap. `fix_family = none`.

---

## Card 38 — Current Monitor (Real-Time)

Filled: three phase series (current_r/y/b), Max (40.5, `current_max`), Min (37.125, `current_min`), Neutral (2.93, `current_neutral`), legend R/Y/B, all time axes.

### Blank data leaves

- **`.metrics[2].value` (Average)** — ref 116.3 A, v48 `null`.
  - Bound `column=current_avg, source=live` — but `current_avg` is **all-null** on this meter, while `current_r/current_y/current_b` are all present (49021 rows each; last row 47.85 / 46.05 / 45.375).
  - Max and Min are effectively phase extremes; Average is the only phase aggregate the meter didn't materialize.
  - **Verdict: derivation_gap (FIXABLE).** Inputs exist → derive Average as mean(current_r, current_y, current_b) at fill time when `current_avg` is null. `fix_family = avg_from_phases_derivation`.

- **`.thresholds[0].value`** — ref 120, v48 `null`. Demo const 1600 with no DB source.
- **`.thresholds[1].value`** — ref 100, v48 `null`. Demo const 0 with no DB source.
  - No nameplate table, no rated-current / CT column on the meter → no honest source for a current limit.
  - **Verdict: honest_absent** (current-limit nameplate/ampacity absent; unlike voltage there is no statutory current band to canonical-fill). `fix_family = current_threshold_nameplate_absent`.

---

## Summary of fixable vs honest

| card | leaf | verdict | fixable? | fix_family |
|---|---|---|---|---|
| 36 | reactiveEnergy.value/displayValue | honest_absent | no | reactive_energy_absent |
| 37 | (thresholds) | filled via canonical band | n/a | — |
| 38 | metrics[2] Average | derivation_gap | YES | avg_from_phases_derivation |
| 38 | thresholds[0] | honest_absent | no | current_threshold_nameplate_absent |
| 38 | thresholds[1] | honest_absent | no | current_threshold_nameplate_absent |

One genuine fixable gap on this page: **card 38 current Average** should be derived from the present per-phase current columns when `current_avg` is null.
