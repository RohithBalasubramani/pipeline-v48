# Card audit — individual-feeder-meter-shell/real-time-monitoring

Meter table: `gic_15_n3_pcc_01_transformer_01_se` (asset GIC-15-N3-PCC-01, mfm 171)
Cards: 36 Power & Energy, 37 Voltage Monitor, 38 Current Monitor.

## Meter probe (last 7 days, non-null counts)

| column | non-null | note |
|---|---|---|
| reactive_energy_import_kvarh | 0 | present but ALL NULL |
| reactive_energy_export_kvarh | 0 | present but ALL NULL |
| apparent_energy_kvah | 49021 | has data (but WRONG quantity for a kvarh slot) |
| current_avg | 0 | present but ALL NULL |
| current_max | 49021 | has data |
| current_min | 49021 | has data |
| current_neutral | 49021 | has data |
| current_r / current_y / current_b | 49022 each | has data (derived avg ≈ 45.34, consistent with max 47.0 / min 43.5) |

---

## Card 36 — Power & Energy (Real-Time)

Real leaves activePower / activeEnergy / apparentPower / reactivePower / projectedDemand all filled from live columns. Two blank leaves:

- **`.readings.reactiveEnergy.value`** (ref 4562, v48 "—")
  - DI: `source="frame"`, `metric="apparent_energy_kvah"`, `column=null`. The emitter tried a cross-unit proxy (kvah → kvarh slot) and `_normalized` correctly blocked it as an undeclared/unmorphed proxy.
  - The NATURAL columns for reactive energy — `reactive_energy_import_kvarh` / `reactive_energy_export_kvarh` — are **present but 100% NULL** on this meter.
  - `apparent_energy_kvah` has data, but it is a DIFFERENT quantity; binding it would fabricate reactive energy from apparent energy. Correctly refused.
  - **Verdict: honest_absent** (`reactive_energy_absent`). EMS shows 4562 because it reads a richer meter; V48 is correct to blank. No fabrication.

- **`.readings.reactiveEnergy.displayValue`** (ref "4562", v48 "—")
  - Chrome mirror / formatted string of the same absent value. Same root cause.
  - **Verdict: honest_absent** (`reactive_energy_absent`).

## Card 37 — Voltage Monitor (Real-Time)

No candidate gaps. metrics (Average/Max/Min = voltage_avg/max/min live) and thresholds (Max 6985.9V / Min 5715.8V from the IS-12360 statutory band via canonical_slots) are all filled. Nothing to fix.

## Card 38 — Current Monitor (Real-Time)

- **`.metrics[2].value`** — "Average" (ref "116.3 A", v48 null)
  - DI: `kind=raw`, `column="current_avg"`, `source="live"`. But `current_avg` is **present-but-ALL-NULL** on this meter, while Max (`current_max`) and Min (`current_min`) both populate fine, and the three phase currents `current_r/y/b` all have data.
  - The average is directly derivable as mean(current_r, current_y, current_b) ≈ 45.34 A — inputs exist, this is NOT fabrication.
  - **Verdict: derivation_gap (FIXABLE)** (`current_avg_derive_from_phases`). Rebind Average to a mean-of-phase-currents derivation (or the meter's own avg register if it ever backfills) instead of the dead `current_avg` raw column.

- **`.thresholds[0].value`** (ref 120, v48 null) and **`.thresholds[1].value`** (ref 100, v48 null)
  - DI honest-blanked: declared consts (1600 / 100) with no measured column and no nameplate/app_config `consts.*` source. `asset_nameplate` does not exist in the neuract schema; no rated-current column on the meter.
  - These are CT/breaker rating reference lines. Unlike voltage (IS-12360 statutory band), there is no statutory current band and no nameplate rated-current to bind. The EMS 120/100 are storybook constants.
  - **Verdict: honest_absent** (`current_threshold_rating_absent`). Would only become bindable if a nameplate rated-current were seeded into cmd_catalog/app_config.

---

## Fix-family rollup

| fix_family | leaves | fixable? |
|---|---|---|
| reactive_energy_absent | card36 reactiveEnergy.value, .displayValue | no (register dead on this meter) |
| current_avg_derive_from_phases | card38 metrics[2].value | YES — derive mean(current_r/y/b) |
| current_threshold_rating_absent | card38 thresholds[0], [1] | no (no nameplate rated-current source) |
